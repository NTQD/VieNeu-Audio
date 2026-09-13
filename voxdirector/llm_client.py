"""Wrapper duy nhất cho Gemini API — mọi Agent gọi LLM qua đây, không tự
import google-genai riêng lẻ. Giúp đổi model/provider ở 1 chỗ duy nhất nếu
cần sau này.
"""

import json
import time

from voxdirector.config import GEMINI_API_KEY, GEMINI_MAX_OUTPUT_TOKENS, GEMINI_MODEL

_client = None  # client mac dinh cua server, dung khi khong co BYOK key
_client_by_key = {}  # api_key -> genai.Client, cache rieng cho tung BYOK key

# Số lần thử lại tối đa khi gặp lỗi 5xx tạm thời (KHÔNG áp dụng cho lỗi 4xx
# như 429/404 — retry không giải quyết được vấn đề billing/model sai, chỉ
# tốn thêm quota vô ích). Xác nhận CÓ THẬT khi test Agent Alpha
# (2026-09-08): "gemini-3.6-flash" trả 503 UNAVAILABLE ("high demand") ngẫu
# nhiên ở khoảng 1/3 lượt gọi thật — không phải giả định, đo được trực tiếp.
_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 2.0  # nhân đôi mỗi lần thử lại: 2s, 4s, 8s


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


def call_structured(system_prompt, user_content, response_schema, api_key: str | None = None):
    """Gọi Gemini với JSON mode bắt buộc — trả về dict đã parse theo
    response_schema (Pydantic model class).

    KHÔNG dùng cách "please return JSON" bằng free text — dùng đúng cơ chế
    structured output/JSON mode của Gemini (response_mime_type +
    response_schema) để tránh model trả markdown fences hoặc giải thích xen
    lẫn JSON.

    Model được GHIM CỨNG theo config.GEMINI_MODEL cho MỌI lệnh gọi trong 1
    lần chạy pipeline — không dùng auto-routing/multi-provider, để kết quả
    có thể tái lập (xem Section 7 của spec).

    api_key: BYOK - key riêng của người dùng gửi kèm request (Section 13 của
    spec, đã được đội ngũ chốt 2026-09-10). None thì dùng key mặc định của
    server (xem _get_client())."""
    from google.genai import errors, types

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

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL, contents=user_content, config=config,
            )
            break
        except errors.ServerError as e:
            # Lỗi 5xx tạm thời (vd. 503 "high demand") — thử lại với backoff
            # tăng dần. Lỗi 4xx (ClientError — sai model, hết quota/billing)
            # KHÔNG retry ở đây, để lộ ra ngay cho người gọi xử lý.
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF_S * (2 ** attempt))
    else:
        raise last_error

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
