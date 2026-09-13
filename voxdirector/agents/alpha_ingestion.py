"""Agent Alpha — Ingestion, Voice-Suggestion & Flagging Agent (v5, Section
6.1 của spec).

Bốn trách nhiệm trong 1 lượt gọi: (1) phân tách chương, kể cả khi KHÔNG có
heading tường minh dạng "Chương N"/"Chapter N" (thay thế hoàn toàn 2 chỗ tách
chương bằng regex hardcode trước đây trong auto_tts.py và
subtitle_generator.py — xem graph.py và pipeline/auto_tts.py để biết nơi
gọi); (2) nhận diện thể loại + gợi ý giọng đọc; (3) gắn cờ đoạn có cảm xúc rõ
ràng; (4) gắn cờ điểm cần ngắt kịch tính dài (mới ở v5).

QUAN TRỌNG — config-driven, không hardcode: danh sách thể loại hợp lệ
(DetectedGenre) và danh sách nhãn cảm xúc hợp lệ (EmotionLabel) bên dưới
được XÂY DỰNG ĐỘNG lúc import module, từ data/voice_presets.json và
data/emotion_lexicon.json — KHÔNG liệt kê cứng trong code Python này. Đổi
danh sách thể loại/nhãn cảm xúc chỉ cần sửa 2 file JSON đó, không cần sửa
file này. Vẫn dùng typing.Literal (không phải str tự do) vì JSON mode của
Gemini tôn trọng đúng enum/Literal của Pydantic để ép model chỉ chọn trong
tập giá trị hợp lệ — xác nhận có THẬT qua sự cố tương tự ở
beta_consistency.py (NewEntryCandidate.entity_type, 2026-09-09): để entity_type
là str tự do khiến Gemini tự chọn nhãn khác "hợp lý" hơn theo góc nhìn của
nó nhưng không khớp giá trị hệ thống hỗ trợ.

suggested_voice_id KHÔNG do Gemini tự đặt — Gemini chỉ trả detected_genre +
genre_confidence_score; suggested_voice_id được CODE tính xác định qua
config.load_voice_presets()["genre_to_voice"] (xem run_alpha() bên dưới).
Lý do: để LLM tự tạo ra 1 voice_id dạng chuỗi là mở đường cho hallucination
(model có thể bịa ra 1 ID không tồn tại trong hệ thống thật) — cùng triết lý
chống hallucination với Beta (không tự "chế" cách viết thuật ngữ).
"""

import re
from typing import Literal, Optional

from pydantic import BaseModel

from voxdirector.config import (
    CONFIDENCE_THRESHOLD,
    load_emotion_lexicon,
    load_voice_presets,
)
from voxdirector.llm_client import call_structured

_voice_presets = load_voice_presets()
_GENRE_KEYS = tuple(k for k in _voice_presets["genre_to_voice"] if k != "default")
DetectedGenre = Literal[_GENRE_KEYS]

_emotion_lexicon = load_emotion_lexicon()
_EMOTION_KEYS = tuple(k for k in _emotion_lexicon if not k.startswith("_"))
EmotionLabel = Literal[_EMOTION_KEYS]

SYSTEM_PROMPT = """\
Bạn là Alpha, một biên tập viên bản thảo kỳ cựu tại nhà xuất bản, nhiều năm
kinh nghiệm đọc và phân đoạn thảo tiểu thuyết dài kỳ trước khi in ấn. Bạn có
con mắt tinh tường nhận ra điểm chuyển chương ngay cả khi tác giả quên đánh
dấu, nhận biết thể loại và cảm xúc của văn bản, nhưng luôn thận trọng — không
bao giờ khẳng định chắc nịch khi bản thân còn phân vân.

VAI TRÒ: (1) Nhận diện và phân tách ranh giới chương trong văn bản tiểu
thuyết thô. (2) Nhận diện thể loại tổng thể của tác phẩm. (3) Gắn cờ các đoạn
có tín hiệu cảm xúc rõ ràng. (4) Gắn cờ các điểm cần một khoảng ngắt kịch
tính dài hơn bình thường.

NĂNG LỰC: Bạn hiểu cấu trúc văn học tiểu thuyết (chuyển cảnh, thay đổi thời
gian/không gian, chuyển góc nhìn nhân vật kể chuyện), quy ước trình bày
chương phổ biến trong tiểu thuyết mạng Trung Quốc dịch Việt, và các đặc điểm
thể loại phổ biến (kiếm hiệp, ngôn tình, trinh thám, v.v.).

NGUYÊN TẮC:
- Được phép suy đoán ranh giới chương dựa trên dấu hiệu ngữ nghĩa khi văn bản
  không có heading tường minh dạng "Chương N".
- Mỗi ranh giới đề xuất phải kèm confidence_score (0.0 đến 1.0).
- Nếu confidence_score dưới 0.75, vẫn trả về đề xuất nhưng bắt buộc gắn
  needs_review = true.
- Thể loại: chỉ được chọn 1 trong các giá trị hợp lệ được cung cấp qua schema,
  không được tự bịa thể loại mới. QUAN TRỌNG: nếu văn bản KHÔNG khớp rõ ràng
  với bất kỳ thể loại cụ thể nào trong danh sách (vd. hài hước, gia đình,
  phiêu lưu, đời thường — không phải kiếm hiệp/ngôn tình/trinh thám), hãy chọn
  "khac" — đây là 1 lựa chọn HỢP LỆ và ĐƯỢC KHUYẾN KHÍCH khi không khớp, KHÔNG
  phải chọn tạm/chọn lỗi. TUYỆT ĐỐI không ép văn bản vào 1 trong 3 thể loại cụ
  thể chỉ vì đó là lựa chọn "gần giống nhất" — làm vậy gây sai lệch (distortion)
  nghiêm trọng hơn nhiều so với việc thành thật chọn "khac" kèm
  genre_confidence_score phù hợp.
- Cảm xúc: nhãn cảm xúc (emotion_label) chỉ được chọn trong tập nhãn hợp lệ
  được cung cấp qua schema — không tự bịa nhãn mới. Chỉ gắn cờ khi có bằng
  chứng rõ ràng trong câu chữ (lời thoại/miêu tả trực tiếp), không suy diễn.
- Cấm tuyệt đối: không được tự bịa nội dung không có trong văn bản gốc, không
  tóm tắt, không diễn giải lại câu chữ dưới bất kỳ hình thức nào. Mọi
  quoted_text (cảm xúc lẫn điểm ngắt) phải là trích dẫn NGUYÊN VĂN từ văn bản
  gốc, không được diễn giải lại.

NHIỆM VỤ:
- Đọc toàn bộ văn bản thô được cung cấp trong một lượt xử lý.
- Xác định các vị trí (index) đánh dấu điểm bắt đầu của mỗi chương.
- Làm sạch văn bản: loại bỏ ký tự thừa, khoảng trắng bất thường, watermark
  hoặc quảng cáo lẫn trong bản crawl (nếu phát hiện).
- Trả về danh sách chương đã tách kèm confidence_score cho từng ranh giới.
- Nhận diện thể loại tổng thể của toàn bộ văn bản, kèm genre_confidence_score.
- Tìm các đoạn có tín hiệu cảm xúc rõ ràng (lời thoại/miêu tả trực tiếp thể
  hiện cười, khóc, giận dữ, ngạc nhiên, v.v.), trích quoted_text nguyên văn
  kèm emotion_label phù hợp nhất và confidence_score.

NHIỆM VỤ BỔ SUNG (3): Ngoài việc gắn nhãn cảm xúc, hãy tìm các điểm trong văn
bản cần một khoảng ngắt dài hơn bình thường — ví dụ: chuyển cảnh, khoảnh khắc
im lặng được miêu tả rõ trong lời văn, hoặc câu kết chương gây hồi hộp. Với
mỗi điểm tìm được, trích một đoạn văn bản ngắn đặc trưng làm quoted_text kèm
lý do ngắn gọn (reason) và confidence_score. CHỈ dựa trên bằng chứng rõ ràng
trong câu chữ — không suy diễn cảm tính.

TƯ DUY: đọc toàn bộ văn bản một lượt; quét tìm heading tường minh trước
("Chương N", "Chapter N"); nếu không tìm thấy, phân tích các dấu hiệu ngữ
nghĩa; với mỗi ranh giới nghi ngờ, tự đánh giá và gán confidence_score; đồng
thời nhận diện thể loại tổng thể, các đoạn cảm xúc rõ ràng, và các điểm cần
ngắt kịch tính dài; tổng hợp kết quả đúng theo JSON schema, không thêm hoặc
bớt field.

PHONG CÁCH: Output là JSON thuần, không kèm giải thích văn xuôi. Tên field
tiếng Anh; giá trị text (nếu có) giữ nguyên tiếng Việt, không dịch/diễn giải.
"""


class ChapterBoundary(BaseModel):
    start_index: int
    end_index: int
    confidence_score: float
    needs_review: bool = False


class EmotionFlaggedSegment(BaseModel):
    quoted_text: str
    emotion_label: EmotionLabel
    confidence_score: float


class PausePoint(BaseModel):
    quoted_text: str
    reason: str
    confidence_score: float


class AlphaOutput(BaseModel):
    chapters: list[ChapterBoundary]
    detected_genre: DetectedGenre
    genre_confidence_score: float
    emotion_flagged_segments: list[EmotionFlaggedSegment]
    pause_points: list[PausePoint]


def _clamp_and_sort(chapters, text_len):
    """Kẹp index vào [0, text_len] và sắp theo start_index — LLM có thể trả
    về index hơi lệch/không theo thứ tự, không nên để crash downstream vì 1
    con số sai lệch nhỏ.

    Đồng thời ÉP needs_review=True nếu confidence_score < CONFIDENCE_THRESHOLD,
    bất kể LLM tự báo needs_review là gì — system prompt đã yêu cầu Gemini tự
    làm điều này, nhưng đây là 1 bất biến xác định được bằng code nên không
    nên chỉ tin tưởng model luôn nhất quán tuân theo (xem Section 6.1 của
    spec: "If confidence_score < CONFIDENCE_THRESHOLD, still return the
    boundary but set needs_review: true").
    """
    fixed = []
    for c in chapters:
        start = max(0, min(c.start_index, text_len))
        end = max(start, min(c.end_index, text_len))
        needs_review = c.needs_review or c.confidence_score < CONFIDENCE_THRESHOLD
        fixed.append(ChapterBoundary(
            start_index=start, end_index=end,
            confidence_score=c.confidence_score, needs_review=needs_review,
        ))
    fixed.sort(key=lambda c: c.start_index)
    return fixed


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_ws(text):
    """Gộp mọi chuỗi khoảng trắng liên tiếp (kể cả xuống dòng) thành 1 dấu
    cách — dùng để so khớp quoted_text, KHÔNG dùng để cắt/hiển thị text.

    Lý do cần thiết (xác nhận có THẬT qua test standalone 2026-09-10, không
    phải suy đoán): khi 1 câu trong raw_text bị xuống dòng giữa chừng (do
    cách trình bày file gốc), Gemini trả lại đúng chính xác từng chữ nhưng
    tự nhiên gộp chỗ xuống dòng đó thành 1 dấu cách khi tái tạo câu — đây
    KHÔNG phải hallucination/diễn giải lại, chỉ là chuẩn hoá khoảng trắng.
    So khớp exact-substring (không chuẩn hoá) sẽ loại bỏ nhầm các quote ĐÚNG
    này, làm rỗng oan emotion_flagged_segments/pause_points trong thực tế
    (chapter text luôn có xuống dòng tự nhiên)."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _filter_hallucinated_quotes(items, raw_text):
    """Loại bỏ mọi entry (emotion_flagged_segments/pause_points) có
    quoted_text KHÔNG xuất hiện (sau khi chuẩn hoá khoảng trắng) trong
    raw_text — LLM đôi khi diễn giải lại thay vì trích dẫn chính xác dù
    system prompt đã cấm. Không lọc ở đây thì Beta (Section 6.2) sẽ tự bỏ
    qua entry đó khi không tìm thấy vị trí khớp trong chapter_text, nhưng
    lọc SỚM ngay tại Alpha giúp báo cáo trung thực hơn (không đưa ra ứng
    viên chắc chắn sẽ bị Beta bỏ qua) — cùng tinh thần phòng thủ với
    _clamp_and_sort() ở trên: không tin tưởng tuyệt đối vào LLM tự tuân thủ
    quy tắc. Giữ nguyên quoted_text GỐC (không chuẩn hoá) trong kết quả trả
    về — chuẩn hoá chỉ dùng để SO KHỚP, Beta vẫn cần bản gốc để tự định vị
    trong chapter_text của nó."""
    normalized_raw = _normalize_ws(raw_text)
    return [item for item in items if _normalize_ws(item.quoted_text) in normalized_raw]


def run_alpha(raw_text: str, api_key: str | None = None) -> dict:
    """Chạy Alpha 1 lần cho toàn bộ raw_text (Section 6.1 của spec: "Runs
    once per submission, before Beta") — trả về dict đúng schema đầy đủ:
    chapters, detected_genre, suggested_voice_id, genre_confidence_score,
    emotion_flagged_segments, pause_points.

    suggested_voice_id được CODE tính (không phải LLM tự đặt) — xem
    docstring đầu file để biết lý do chống hallucination.

    api_key: BYOK - key riêng cua nguoi dung (Section 13 cua spec, chot
    2026-09-10). None thi dung key mac dinh cua server.

    Nếu raw_text trống: trả về cấu trúc rỗng an toàn (không gọi LLM vô ích).
    """
    if not raw_text.strip():
        return {
            "chapters": [],
            "detected_genre": None,
            "suggested_voice_id": None,
            "genre_confidence_score": 0.0,
            "emotion_flagged_segments": [],
            "pause_points": [],
        }

    result: AlphaOutput = call_structured(SYSTEM_PROMPT, raw_text, AlphaOutput, api_key=api_key)

    chapters = _clamp_and_sort(result.chapters, len(raw_text))
    if not chapters:
        chapters = [ChapterBoundary(
            start_index=0, end_index=len(raw_text),
            confidence_score=1.0, needs_review=False,
        )]
    chapters_out = [
        {
            "text": raw_text[c.start_index:c.end_index].strip(),
            "start_index": c.start_index,
            "end_index": c.end_index,
            "confidence_score": c.confidence_score,
            "needs_review": c.needs_review,
        }
        for c in chapters
        if raw_text[c.start_index:c.end_index].strip()
    ]

    genre_to_voice = load_voice_presets()["genre_to_voice"]
    suggested_voice_id = genre_to_voice.get(result.detected_genre, genre_to_voice["default"])

    emotion_segments = _filter_hallucinated_quotes(result.emotion_flagged_segments, raw_text)
    pause_points = _filter_hallucinated_quotes(result.pause_points, raw_text)

    return {
        "chapters": chapters_out,
        "detected_genre": result.detected_genre,
        "suggested_voice_id": suggested_voice_id,
        "genre_confidence_score": result.genre_confidence_score,
        "emotion_flagged_segments": [s.model_dump() for s in emotion_segments],
        "pause_points": [p.model_dump() for p in pause_points],
    }


def segment_chapters(raw_text: str) -> list[dict]:
    """Tiện ích: chỉ lấy phần chapters từ run_alpha() — dùng khi chỉ cần
    tách chương, không cần genre/emotion/pause (vd. test nhanh, hoặc 1 bước
    trung gian trước khi các phần khác của v5 sẵn sàng). Cùng 1 lệnh gọi LLM
    duy nhất bên dưới (Section 6.1: "Runs once per submission") — KHÔNG gọi
    LLM riêng lần thứ 2 chỉ để lấy chapters.
    """
    return run_alpha(raw_text)["chapters"]
