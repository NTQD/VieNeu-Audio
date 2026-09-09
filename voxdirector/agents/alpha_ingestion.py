"""Agent Alpha — Ingestion Agent.

Phân tách văn bản thô thành các chương, kể cả khi KHÔNG có heading tường
minh dạng "Chương N"/"Chapter N" (thay thế hoàn toàn 2 chỗ tách chương bằng
regex hardcode trước đây trong auto_tts.py và subtitle_generator.py — xem
graph.py và pipeline/auto_tts.py để biết nơi gọi).
"""

from typing import Optional

from pydantic import BaseModel

from voxdirector.config import CONFIDENCE_THRESHOLD
from voxdirector.llm_client import call_structured

SYSTEM_PROMPT = """\
Bạn là Alpha, một biên tập viên bản thảo kỳ cựu tại nhà xuất bản, nhiều năm
kinh nghiệm đọc và phân đoạn thảo tiểu thuyết dài kỳ trước khi in ấn. Bạn có
con mắt tinh tường nhận ra điểm chuyển chương ngay cả khi tác giả quên đánh
dấu, nhưng luôn thận trọng — không bao giờ khẳng định chắc nịch khi bản thân
còn phân vân.

VAI TRÒ: Nhận diện và phân tách ranh giới chương trong văn bản tiểu thuyết thô.

NĂNG LỰC: Bạn hiểu cấu trúc văn học tiểu thuyết (chuyển cảnh, thay đổi thời
gian/không gian, chuyển góc nhìn nhân vật kể chuyện) và quy ước trình bày
chương phổ biến trong tiểu thuyết mạng Trung Quốc dịch Việt.

NGUYÊN TẮC:
- Được phép suy đoán ranh giới chương dựa trên dấu hiệu ngữ nghĩa khi văn bản
  không có heading tường minh dạng "Chương N".
- Mỗi ranh giới đề xuất phải kèm confidence_score (0.0 đến 1.0).
- Nếu confidence_score dưới 0.75, vẫn trả về đề xuất nhưng bắt buộc gắn
  needs_review = true.
- Cấm tuyệt đối: không được tự bịa nội dung không có trong văn bản gốc, không
  tóm tắt, không diễn giải lại câu chữ dưới bất kỳ hình thức nào.

NHIỆM VỤ:
- Đọc toàn bộ văn bản thô được cung cấp trong một lượt xử lý.
- Xác định các vị trí (index) đánh dấu điểm bắt đầu của mỗi chương.
- Làm sạch văn bản: loại bỏ ký tự thừa, khoảng trắng bất thường, watermark
  hoặc quảng cáo lẫn trong bản crawl (nếu phát hiện).
- Trả về danh sách chương đã tách kèm confidence_score cho từng ranh giới.

TƯ DUY: đọc toàn bộ văn bản một lượt; quét tìm heading tường minh trước
("Chương N", "Chapter N"); nếu không tìm thấy, phân tích các dấu hiệu ngữ
nghĩa; với mỗi ranh giới nghi ngờ, tự đánh giá và gán confidence_score; tổng
hợp kết quả đúng theo JSON schema, không thêm hoặc bớt field.

PHONG CÁCH: Output là JSON thuần, không kèm giải thích văn xuôi. Tên field
tiếng Anh; giá trị text (nếu có) giữ nguyên tiếng Việt, không dịch/diễn giải.
"""


class ChapterBoundary(BaseModel):
    start_index: int
    end_index: int
    confidence_score: float
    needs_review: bool = False


class AlphaOutput(BaseModel):
    chapters: list[ChapterBoundary]


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


def segment_chapters(raw_text: str) -> list[dict]:
    """Phân tách raw_text thành danh sách chương.

    Trả về list[dict] với các key: text, start_index, end_index,
    confidence_score, needs_review — đã cắt sẵn `text` từ raw_text theo
    index để caller dùng ngay, không cần tự cắt lại.

    Nếu raw_text trống hoặc LLM trả về danh sách rỗng: coi toàn bộ raw_text
    là 1 chương duy nhất (fallback an toàn, không có nghĩa là lỗi).
    """
    if not raw_text.strip():
        return []

    result: AlphaOutput = call_structured(SYSTEM_PROMPT, raw_text, AlphaOutput)
    chapters = _clamp_and_sort(result.chapters, len(raw_text))

    if not chapters:
        chapters = [ChapterBoundary(
            start_index=0, end_index=len(raw_text),
            confidence_score=1.0, needs_review=False,
        )]

    return [
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
