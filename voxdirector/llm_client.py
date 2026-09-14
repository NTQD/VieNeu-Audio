"""Wrapper duy nhất cho Gemini API — mọi Agent gọi LLM qua đây, không tự
import google-genai riêng lẻ. Giúp đổi model/provider ở 1 chỗ duy nhất nếu
cần sau này.
"""

import json
import threading
import time

from voxdirector.config import (
    GEMINI_API_KEY,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_MODEL,
    GEMINI_MODEL_FALLBACKS,
)

_client = None  # client mac dinh cua server, dung khi khong co BYOK key
_client_by_key = {}  # api_key -> genai.Client, cache rieng cho tung BYOK key

# Số lần thử lại tối đa khi gặp lỗi 5xx tạm thời (KHÔNG áp dụng cho lỗi 4xx
# như 429/404 — retry không giải quyết được vấn đề billing/model sai, chỉ
# tốn thêm quota vô ích). Xác nhận CÓ THẬT khi test Agent Alpha
# (2026-09-08): "gemini-3.6-flash" trả 503 UNAVAILABLE ("high demand") ngẫu
# nhiên ở khoảng 1/3 lượt gọi thật — không phải giả định, đo được trực tiếp.
_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 2.0  # nhân đôi mỗi lần thử lại: 2s, 4s, 8s

# Model resilience (muc 17 cua master plan, xem chu thich day du o
# config.GEMINI_MODEL_FALLBACKS) - resolve 1 LAN cho ca tien trinh, luc lan
# goi call_structured() dau tien THUC SU chay xong (thanh cong voi model
# nao thi CACHE lai model do cho MOI lan goi ve sau, khong resolve lai giua
# chung 1 job dang chay). None nghia la CHUA resolve.
_active_model: str | None = None
_active_model_lock = threading.Lock()


def _get_client(api_key: str | None = None):
    """Khởi tạo Gemini client. BYOK (2026-09-10, theo yêu cầu người dùng —
    "users will use their own API key, we use their key for their own use"):
    nếu api_key được truyền vào (từ request của người dùng), dùng ĐÚNG key đó
    thay vì key mặc định của server — cache riêng theo từng key (nhiều người
    dùng khác nhau, key khác nhau, không dùng chung 1 client). Không truyền
    api_key: dùng client mặc định của server (config.GEMINI_API_KEY) — giữ
    tương thích ngược cho dev cục bộ / fallback khi người dùng chưa nhập key
    riêng."""
    from google import genai

    if api_key:
        if api_key not in _client_by_key:
            _client_by_key[api_key] = genai.Client(api_key=api_key)
        return _client_by_key[api_key]

    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "Thiếu GEMINI_API_KEY (hoặc GOOGLE_API_KEY) trong biến môi trường, "
                "VÀ người dùng chưa nhập API key riêng (BYOK) trong Cài đặt. "
                "Cần ít nhất 1 trong 2."
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _generate_with_retry(client, model: str, user_content, config):
    """Goi generate_content voi 1 model CO DINH, thu lai toi da _MAX_RETRIES
    lan CHI cho loi 5xx tam thoi (backoff tang dan). Loi 4xx (ClientError)
    nem ra NGAY o lan dau, khong retry - xem ly do o docstring cu cua
    call_structured() truoc day (van dung nguyen)."""
    from google.genai import errors

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            return client.models.generate_content(
                model=model, contents=user_content, config=config,
            )
        except errors.ServerError as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF_S * (2 ** attempt))
    raise last_error


def _resolve_model(client, user_content, config) -> tuple[object, str]:
    """Xac dinh model se dung cho CA TIEN TRINH nay (xem
    config.GEMINI_MODEL_FALLBACKS) - CHI chay logic tim fallback o LAN GOI
    DAU TIEN (khi _active_model con la None); sau khi 1 model da thanh cong,
    moi lan goi sau CHI dung dung model do, khong tim lai (giu dung nguyen
    tac "1 model ghim cung/lan chay" cua GEMINI_MODEL). Tra ve
    (response, model_da_dung) cua chinh lan goi thanh cong dau tien, de khoi
    phai goi lai generate_content 1 lan nua cho model do.

    QUAN TRONG: lock CHI bao quanh phan doc/ghi _active_model (1 phep gan
    bien, tuc thi), KHONG bao quanh luc goi generate_content that su qua
    mang - VPS co nhieu job dong thoi (nhieu user) se goi ham nay tu nhieu
    luong/task cung luc; giu lock trong luc cho response se lam TOAN BO Gemini
    call cua ca server bi tuan tu hoa (1 job phai doi job khac goi API xong
    moi duoc goi) - can tranh loi nay khi thiet ke tinh nang resilience nay."""
    global _active_model
    from google.genai import errors

    with _active_model_lock:
        model = _active_model
    if model is not None:
        response = _generate_with_retry(client, model, user_content, config)
        return response, model

    # Chua resolve lan nao - nhieu job dong thoi co the cung roi vao nhanh
    # nay truoc khi 1 job nao thanh cong (chi xay ra 1 lan luc tien trinh
    # moi khoi dong/sau restart, khong lap lai) - chap nhan vai lan goi API
    # trung lap trong truong hop hiem nay, doi lay viec KHONG serialize toan
    # bo server.
    candidates = [GEMINI_MODEL, *GEMINI_MODEL_FALLBACKS]
    last_error = None
    for i, candidate_model in enumerate(candidates):
        try:
            response = _generate_with_retry(client, candidate_model, user_content, config)
        except errors.ServerError as e:
            # Da het luot retry 5xx tam thoi cho model nay (vd. 503 "high
            # demand" lien tuc) - thu model du phong tiep theo.
            last_error = e
            continue
        except errors.ClientError as e:
            if e.code == 404:
                # Model nay khong ton tai/da bi go bo cho key nay - ro rang
                # la van de CUA MODEL, thu model du phong tiep theo.
                last_error = e
                continue
            # Loi 4xx khac (401/403 sai key, 429 het quota, 400 request sai)
            # KHONG lien quan gi den viec chon model - doi model khac cung
            # se loi y het, chi lam cham viec bao loi that su. Nem ra NGAY,
            # giu dung nguyen tac cu (khong retry 4xx).
            raise
        else:
            with _active_model_lock:
                if _active_model is None:
                    _active_model = candidate_model
                    if i > 0:
                        print(
                            f"[VoxDirector] CANH BAO: model chinh '{GEMINI_MODEL}' khong "
                            f"dung duoc ({last_error}), da chuyen sang model du phong "
                            f"'{candidate_model}' cho toi khi backend restart."
                        )
            return response, candidate_model
    # Het CA danh sach candidates (chinh + du phong, neu co) ma khong model
    # nao dung duoc - nem lai DUNG loi goc cua candidate CUOI CUNG (giu
    # nguyen kieu ngoai le that su, vd. errors.ServerError/errors.ClientError)
    # thay vi boc trong 1 RuntimeError moi: (1) code goi call_structured() o
    # noi khac co the dang bat DUNG kieu loi nay (xem tests/test_llm_client.py),
    # (2) khi CHI CO 1 candidate (GEMINI_MODEL_FALLBACKS rong - mac dinh),
    # day chinh la hanh vi CU truoc khi tinh nang nay ton tai, khong nen doi.
    if len(candidates) > 1:
        print(
            f"[VoxDirector] CANH BAO: khong co model Gemini nao trong {candidates} "
            f"dung duoc (kiem tra config.GEMINI_MODEL_FALLBACKS neu can them model "
            f"du phong THAT SU con duoc cap - xem aistudio.google.com)."
        )
    raise last_error


def call_structured(system_prompt, user_content, response_schema, api_key: str | None = None):
    """Gọi Gemini với JSON mode bắt buộc — trả về dict đã parse theo
    response_schema (Pydantic model class).

    KHÔNG dùng cách "please return JSON" bằng free text — dùng đúng cơ chế
    structured output/JSON mode của Gemini (response_mime_type +
    response_schema) để tránh model trả markdown fences hoặc giải thích xen
    lẫn JSON.

    Model được GHIM CỨNG cho MỌI lệnh gọi trong 1 lần chạy pipeline — không
    tự đổi model giữa các lần gọi của CÙNG 1 job, để kết quả có thể tái lập
    (xem Section 7 của spec). config.GEMINI_MODEL_FALLBACKS cho phép chuyển
    sang model dự phòng nếu model chính không còn dùng được — nhưng chỉ được
    quyết định 1 lần cho cả tiến trình backend (xem _resolve_model()), không
    bao giờ đổi model giữa chừng 1 job đang chạy.

    api_key: BYOK - key riêng của người dùng gửi kèm request (Section 13 của
    spec, đã được đội ngũ chốt 2026-09-10). None thì dùng key mặc định của
    server (xem _get_client())."""
    from google.genai import types

    client = _get_client(api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=response_schema,
        # Xem ghi chu chi tiet o voxdirector.config.GEMINI_MAX_OUTPUT_TOKENS -
        # KHONG bo trong (SDK se dung gia tri mac dinh thap hon nhieu gioi han
        # that cua model, gay cat ngang am tham voi van ban dai - day CHINH LA
        # nguyen nhan loi "chi doc duoc ~80% noi dung roi dung" bao cao 2026-09-12).
        max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
    )

    response, model_used = _resolve_model(client, user_content, config)

    # Muc 18 cua master plan (uoc tinh chi phi/job) - ghi lai SO TOKEN THAT
    # SU da dung (do chinh Gemini API tra ve, khong tu uoc tinh) vao bo dem
    # cua job dang chay (xem voxdirector/usage_tracker.py). Boc try/except
    # rieng - CUNG 1 nguyen tac voi voxdirector/db.py (record_job/record_chapter):
    # 1 loi ghi so lieu PHU TRO (vd. usage_metadata thieu/sai dinh dang o 1
    # phien ban SDK khac, hoac response gia lap trong test khong co field
    # nay) KHONG duoc phep lam gian doan ket qua THAT cua lan goi Gemini nay.
    try:
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            from voxdirector import usage_tracker

            usage_tracker.record(
                model_used,
                int(usage.prompt_token_count or 0),
                int(usage.candidates_token_count or 0),
            )
    except Exception as e:
        print(f"[VoxDirector] Canh bao: khong ghi duoc token usage ({e}) - khong anh huong pipeline.")

    # Xac nhan CO THAT (2026-09-12) - khi Gemini cham gioi han max_output_tokens
    # giua chung 1 chuoi text dai (vd. corrected_text cua Beta, hoac chapters
    # cua Alpha khi ca cuon truyen bi gop thanh 1 chuong), JSON mode van co the
    # tra ve cau truc JSON HOP LE VE CU PHAP (SDK tu dong dong ngoac) nhung NOI
    # DUNG BI CAT MAT - khong nem loi parse, nen PHAI tu kiem tra finish_reason
    # o day va bao loi RO RANG, thay vi de pipeline am tham chay tiep voi du
    # lieu thieu (dung trieu chung nguoi dung bao cao: "doc 80% roi dung").
    candidates = getattr(response, "candidates", None) or []
    if candidates and candidates[0].finish_reason == types.FinishReason.MAX_TOKENS:
        raise RuntimeError(
            f"Gemini đã CẮT NGANG phản hồi vì chạm giới hạn max_output_tokens "
            f"({GEMINI_MAX_OUTPUT_TOKENS} tokens) — nội dung đầu vào (chương/văn "
            f"bản) quá dài để xử lý trong 1 lượt gọi. Đây là lỗi RÕ RÀNG (không "
            f"phải bug cắt ngang âm thầm) — hãy chia nhỏ văn bản/chương thành các "
            f"phần ngắn hơn trước khi gửi lại, hoặc tăng "
            f"VOXDIRECTOR_GEMINI_MAX_OUTPUT_TOKENS nếu model hỗ trợ giới hạn cao hơn."
        )

    # response.parsed đã là instance của response_schema khi SDK parse thành
    # công; fallback về json.loads(response.text) nếu parsed không khả dụng
    # (vd. phiên bản SDK cũ hơn không hỗ trợ .parsed).
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        return parsed
    return response_schema.model_validate(json.loads(response.text))
