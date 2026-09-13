"""Section 7.3 (v5, CÓ ĐIỀU KIỆN — xem Section 11 Step 0 của spec) — ngắt
nghỉ ngắn tại dấu câu bên trong 1 chunk ~250-từ.

LƯU Ý (2026-09-11): Piper đã bị GỠ BỎ HOÀN TOÀN khỏi TTS engine (đảo ngược
quyết định 2026-09-10, quay lại VieNeu-TTS). Toàn bộ phần "CƠ CHẾ" bên dưới
mô tả hành vi CỤ THỂ của Piper (đã xác nhận qua đọc mã nguồn piper-tts lúc
đó) — đây là LỊCH SỬ giải thích vì sao module này tồn tại, KHÔNG còn là mô tả
đúng cho engine hiện tại. Cơ chế tách-mảnh-rồi-tự-ghép-khoảng-lặng
(concat_with_variable_silence) vẫn engine-agnostic và nhiều khả năng tái sử
dụng được, nhưng cần XÁC NHẬN LẠI bằng thực nghiệm với VieNeu-TTS (VieNeu có
thể tự xử lý ngắt nghỉ dấu câu khác với Piper — không giả định giống nhau)
trước khi coi module này là bắt buộc cho engine mới.

CHỈ xây dựng vì Step 0 đã xác nhận THẬT (không suy đoán) là Piper không tự
tạo ngắt nghỉ đủ tự nhiên: dấu phẩy/chấm/hỏi/than chỉ tạo khoảng lặng
23-46ms (dưới ngưỡng cảm nhận rõ rệt của người nghe), còn "..." và dấu gạch
ngang đầu dòng thoại bị espeak-ng ÂM THẦM LOẠI BỎ hoàn toàn trước khi tới
model — xem scratch_check/test_piper_pause_step0.py.

ĐÂY LÀ HÀM RULE-BASED/REGEX THUẦN TUÝ — KHÔNG phải LLM agent, KHÔNG nằm
trong Beta. Khác với sentinel [[PAUSE_LONG]] của Section 7.2 (do Alpha/Beta
đánh dấu dựa trên HIỂU NGỮ CẢNH, ở cấp ranh giới CHUNK): module này hoạt
động ở cấp ĐỘ MỊN HƠN — BÊN TRONG 1 chunk mà text_splitter.py đã tạo ra sẵn
(không phải trước đó) — xác nhận vị trí chính xác trong build order (giữa
Step 6 và Step 7) theo hướng dẫn của người dùng ngày 2026-09-10.

CƠ CHẾ (xác nhận qua đọc trực tiếp mã nguồn piper-tts, KHÔNG suy đoán):
- Piper (gói piper-tts) KHÔNG có cú pháp inline pause/break nào —
  `SynthesisConfig` chỉ có speaker_id/length_scale/noise_scale/noise_w_scale/
  normalize_audio/volume, không có tham số pause. `EspeakPhonemizer.phonemize()`
  (piper/phonemize_espeak.py) gọi `espeakbridge.get_phonemes(text)`, trả về
  đúng (phonemes, terminator, end_of_sentence) — không nhận bất kỳ markup/tag
  nào để chèn ngắt nghỉ tuỳ chỉnh vào. Do đó CHỈ CÒN 1 hướng khả thi: tách
  nhỏ văn bản tại từng dấu câu, tổng hợp audio TỪNG MẢNH riêng qua Piper, rồi
  tự ghép lại bằng khoảng lặng CHÍNH XÁC do chính mình kiểm soát
  (audio_postprocess.concat_with_variable_silence()) — không dựa vào Piper
  tự tạo khoảng lặng gì cả.
- Dấu câu bị XOÁ khỏi văn bản trước khi đưa vào Piper (không giữ lại) — đã
  kiểm chứng THẬT: giữ hay xoá dấu phẩy không làm thay đổi độ dài audio kết
  quả (chênh lệch đo được = 0ms). Xoá là lựa chọn AN TOÀN HƠN và ĐỒNG NHẤT
  hơn giữa mọi loại dấu (một số dấu như "..."/"-" đã bị espeak-ng tự loại bỏ
  từ trước rồi — xoá tất cả theo cùng 1 quy tắc tránh xử lý không đồng nhất).
"""

import json
import os
import re

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PUNCTUATION_PAUSES_PATH = os.path.join(_DATA_DIR, "punctuation_pauses.json")

# Key riêng cho dấu gạch ngang đầu dòng thoại — KHÔNG phải 1 ký tự dấu câu
# thông thường trong bảng, nên không được đưa vào regex dấu câu chung (xem
# _build_punctuation_regex()). Có regex + xử lý RIÊNG, chạy TRƯỚC quy tắc
# dấu gạch ngang thông thường ("-"), để 1 dòng thoại không bị quy tắc gạch
# ngang thông thường bắt nhầm trước.
DIALOGUE_DASH_KEY = "dialogue_dash_line_start"
_DIALOGUE_DASH_RE = re.compile(r"^[ \t]*-[ \t]+", re.MULTILINE)

_cached_table = None


def load_punctuation_pauses(path=None):
    """Nạp bảng tra dấu câu -> thời lượng khoảng lặng (ms) — file do đội ngũ
    tự tải lên (uploadable, xem Section 6.3/7.3 của spec), có cache trong
    tiến trình. path=None dùng đường dẫn mặc định data/punctuation_pauses.json."""
    global _cached_table
    if path is None and _cached_table is not None:
        return _cached_table
    load_path = path or PUNCTUATION_PAUSES_PATH
    with open(load_path, "r", encoding="utf-8") as f:
        table = json.load(f)
    if path is None:
        _cached_table = table
    return table


def invalidate_cache() -> None:
    """Xoa cache trong tien trinh - goi ngay sau khi POST /api/settings/punctuation-pauses
    (backend/app/main.py) ghi de file, de load_punctuation_pauses() doc lai
    TU DIA o lan goi ke tiep thay vi tra ve bang cu da cache. Khac voi
    emotion-lexicon, bang nay KHONG bi dong bang vao 1 kieu Pydantic Literal
    nao - split_chunk_by_punctuation() da goi load_punctuation_pauses() moi
    lan xu ly 1 chunk (khong luu bien dong cung module), nen chi can xoa
    cache la du de thay doi co hieu luc NGAY, khong can restart backend."""
    global _cached_table
    _cached_table = None


def _build_punctuation_regex(table):
    """Xây regex khớp CHÍNH XÁC các dấu câu trong bảng (trừ
    dialogue_dash_line_start — không phải 1 chuỗi ký tự dấu câu thật, xử lý
    riêng). Sắp theo ĐỘ DÀI GIẢM DẦN (dấu dài trước dấu ngắn, vd. "..." và
    "?!" trước "." và "?") để tránh 1 dấu dài bị khớp nhầm thành 1 phần của
    nó bởi 1 dấu ngắn hơn đứng trước trong danh sách."""
    keys = [k for k in table if k not in (DIALOGUE_DASH_KEY, "_placeholder", "_note") and table.get(k) is not None]
    keys_sorted = sorted(keys, key=len, reverse=True)
    return re.compile("|".join(re.escape(k) for k in keys_sorted))


def split_chunk_by_punctuation(chunk_text, table=None):
    """Tách 1 chunk (~250 từ, ĐÃ qua text_splitter.py) thành danh sách các
    mảnh nhỏ hơn tại từng dấu câu được nhận diện — dấu câu bị XOÁ khỏi nội
    dung mảnh (xem docstring đầu file).

    Trả về (pieces, pause_durations_ms):
    - pieces: list[str], N mảnh (rỗng/toàn khoảng trắng đã bị loại bỏ).
    - pause_durations_ms: list[int], N-1 phần tử — khoảng lặng (mili giây)
      giữa pieces[i] và pieces[i+1].

    Nếu chunk_text không có dấu câu nào trong bảng: trả về ([chunk_text], []).
    """
    if table is None:
        table = load_punctuation_pauses()

    dialogue_dash_ms = table.get(DIALOGUE_DASH_KEY, 350)
    punct_re = _build_punctuation_regex(table)

    # Gộp 2 loại "điểm ngắt" (dialogue-dash đầu dòng + dấu câu thường) thành
    # 1 danh sách match duy nhất, SẮP THEO VỊ TRÍ TRONG VĂN BẢN — dialogue-
    # dash được tìm TRƯỚC và ĐÁNH DẤU RIÊNG (kind="dash") để không bị quy
    # tắc dấu gạch ngang thường ("-", kind="punct") bắt trùng vị trí.
    matches = []
    for m in _DIALOGUE_DASH_RE.finditer(chunk_text):
        matches.append((m.start(), m.end(), "dash", None))

    dash_spans = [(s, e) for s, e, _, _ in matches]

    def _overlaps_dash(start, end):
        return any(not (end <= ds or start >= de) for ds, de in dash_spans)

    for m in punct_re.finditer(chunk_text):
        if _overlaps_dash(m.start(), m.end()):
            continue  # đã được xử lý như 1 phần của dialogue-dash ở trên
        matches.append((m.start(), m.end(), "punct", m.group()))

    matches.sort(key=lambda t: t[0])

    pieces = []
    pause_durations_ms = []
    pos = 0

    def _flush_piece(text_before, pause_after_ms):
        """Chốt 1 mảnh văn bản (nếu có nội dung thật) + khoảng lặng sau nó.
        Mảnh rỗng/toàn khoảng trắng bị bỏ qua — nếu đã có mảnh trước đó,
        GIỮ LẠI khoảng lặng lớn hơn giữa lần này và lần trước (max) thay vì
        mất hẳn ý định ngắt nghỉ.

        QUYẾT ĐỊNH TIE-BREAK (có chủ đích, đã kiểm chứng qua test — không
        phải lỗi): áp dụng CHO CẢ trường hợp 2 dấu câu thường liền nhau
        ("?!." không có chữ ở giữa) LẪN trường hợp rất phổ biến trong thực
        tế — 1 câu kết thúc bằng dấu câu, xuống dòng, rồi ngay lập tức là 1
        dòng thoại mới (vd. "...lạnh.\n- Anh đi đâu đấy?"). Về mặt audio chỉ
        có ĐÚNG 1 điểm nối thực sự giữa 2 mảnh lời nói (không có gì được đọc
        ở khoảng xuống dòng đó), nên chỉ có thể chọn 1 khoảng lặng — dùng
        max() để không bao giờ rút ngắn khoảng lặng dự định thấp hơn ý cả
        hai dấu. Nếu dòng trước dialogue-dash CÓ nội dung thật (không chỉ
        khoảng trắng/xuống dòng), dash vẫn nhận đúng giá trị riêng của nó,
        không bị gộp — xem test_dialogue_dash_gets_its_own_350ms_when_preceded_by_real_content."""
        text_before = text_before.strip()
        if not text_before:
            if pieces and pause_durations_ms:
                pause_durations_ms[-1] = max(pause_durations_ms[-1], pause_after_ms)
            return
        pieces.append(text_before)
        pause_durations_ms.append(pause_after_ms)

    for start, end, kind, _matched_text in matches:
        segment = chunk_text[pos:start]
        pause_ms = dialogue_dash_ms if kind == "dash" else table[_matched_text]
        _flush_piece(segment, pause_ms)
        pos = end

    # Mảnh cuối cùng (sau dấu câu cuối cùng, hoặc toàn bộ chunk nếu không có
    # dấu câu nào) — không có khoảng lặng "sau" nó (biên chunk, do
    # audio_postprocess.py xử lý riêng ở cấp Section 7.2/mặc định).
    tail = chunk_text[pos:].strip()
    if tail:
        pieces.append(tail)
    elif pause_durations_ms:
        # Chunk kết thúc ngay sau 1 dấu câu (không còn chữ nào sau) — khoảng
        # lặng đã ghi cho dấu đó không có mảnh nào theo sau để áp dụng giữa
        # 2 mảnh, nên bỏ đi (không phải lỗi, không phải mất mát — biên chunk
        # đã có khoảng lặng riêng).
        pause_durations_ms.pop()

    if not pieces:
        return [chunk_text.strip()] if chunk_text.strip() else [], []

    assert len(pause_durations_ms) == len(pieces) - 1, (
        f"Bat bien vi pham: {len(pieces)} manh nhung {len(pause_durations_ms)} "
        f"khoang lang (can dung {len(pieces) - 1})"
    )
    return pieces, pause_durations_ms
