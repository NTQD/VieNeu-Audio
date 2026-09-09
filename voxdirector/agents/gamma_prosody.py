"""Agent Gamma — Prosody Agent.

Phân loại lời dẫn truyện / lời thoại và gán speaker_id cho từng đoạn.

LƯU Ý QUAN TRỌNG (khác với đặc tả gốc): bản đặc tả ban đầu còn có
`emotion_tag` (gán cảm xúc cho từng đoạn, map sang "emotion cue" của
VieNeu-TTS). Đã BỎ HOÀN TOÀN field này — VieNeu-TTS bản đang cài KHÔNG có
catalog emotion tag nào để map tới (xem ghi chú trong pipeline/auto_tts.py
init_tts() và alpha/beta agent khác — chỉ có duy nhất
"<|emotion_0|>" ứng với emotion="natural", không phải 1 hệ tag cảm xúc thật
sự). Gamma giờ chỉ còn phân loại narration/dialogue + speaker_id.

speaker_id: hiện KHÔNG có cơ chế multi-speaker thật trong SDK VieNeu-TTS
đang cài (đã xác nhận: không có "speaker"/"multi-speaker" nào trong
src/vieneu/) — output của Gamma vẫn được sinh ra và log lại như metadata hữu
ích cho việc render multi-giọng trong tương lai, nhưng KHÔNG được dùng để
tự động chuyển giọng khi render audio ở bước hiện tại (xem graph.py).
"""

from pydantic import BaseModel

from voxdirector.llm_client import call_structured

SYSTEM_PROMPT = """\
Bạn là Gamma, đạo diễn lồng tiếng dày dạn kinh nghiệm chỉ đạo diễn xuất cho
audiobook. Bạn tinh tế trong việc đọc vị vai trò của từng câu chữ — lời dẫn
truyện hay lời thoại nhân vật — nhưng luôn tôn trọng nguyên tác, không bao
giờ suy diễn thêm những gì văn bản gốc không thể hiện rõ.

VAI TRÒ: Phân tích văn bản để phân loại lời thoại/lời dẫn truyện và gán
speaker_id cho từng đoạn thoại.

NGUYÊN TẮC:
- Được phép suy đoán loại người nói (narration/dialogue) và speaker_id dựa
  trên ngữ cảnh, dấu câu, động từ tường thuật.
- Mỗi nhãn gán phải kèm confidence_score. Nếu dưới ngưỡng 0.75, để trống
  (null) speaker_id thay vì đoán đại tên nhân vật.
- Cấm tuyệt đối: không được tự thêm lời thoại hoặc tình tiết không có trong
  văn bản gốc.

NHIỆM VỤ:
- Chia văn bản thành các đoạn nhỏ theo lời dẫn truyện và lời thoại từng nhân
  vật.
- Gán speaker_id cho mỗi đoạn thoại dựa vào tên nhân vật trong ngữ cảnh gần
  nhất (đoạn lời dẫn truyện luôn có speaker_id = null).
- Giữ nguyên nội dung văn bản gốc, chỉ thêm nhãn — không viết lại câu chữ.

TƯ DUY: đọc đoạn văn theo thứ tự; xác định ranh giới lời dẫn/lời thoại qua
dấu ngoặc kép và động từ tường thuật; với mỗi đoạn thoại, truy ngược ngữ cảnh
gần nhất để xác định speaker; gán confidence_score cho từng quyết định.

PHONG CÁCH: Output JSON, field tiếng Anh, giá trị text tiếng Việt. Ưu tiên
null hơn là đoán khi không chắc chắn — nguyên tắc "thà thiếu còn hơn sai" áp
dụng nghiêm ngặt.
"""


class Segment(BaseModel):
    text: str
    segment_type: str  # "narration" | "dialogue"
    speaker_id: str | None = None
    confidence_score: float


class GammaOutput(BaseModel):
    segments: list[Segment]


def tag_segments(text_chunk: str) -> list[dict]:
    """Phân loại narration/dialogue + gán speaker_id cho 1 đoạn text (thường
    là 1 chunk output của text_splitter.py). Trả về list[dict]."""
    if not text_chunk.strip():
        return []
    result: GammaOutput = call_structured(SYSTEM_PROMPT, text_chunk, GammaOutput)
    return [s.model_dump() for s in result.segments]
