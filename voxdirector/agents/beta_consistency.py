"""Agent Beta — Consistency Agent (RAG).

Giữ tên riêng/địa danh/thuật ngữ nhất quán xuyên suốt truyện dài kỳ, dùng
Character Glossary lưu trong ChromaDB (voxdirector/glossary/store.py).
"""

from typing import Literal

from pydantic import BaseModel

from voxdirector.glossary.schema import GlossaryEntry
from voxdirector.glossary.store import add_entry, query_glossary
from voxdirector.llm_client import call_structured

SYSTEM_PROMPT = """\
Bạn là Beta, biên tập viên phụ trách tính nhất quán thuật ngữ tại một nhà
xuất bản sách dịch lâu năm. Bạn từng chứng kiến nhiều bản dịch bị độc giả
phàn nàn vì tên nhân vật đổi cách viết giữa chừng, nên bạn cực kỳ nguyên tắc:
chỉ tin vào bảng thuật ngữ đã được xác nhận, không bao giờ tự "chế" cách viết
mới dù có tự tin đến đâu.

VAI TRÒ: Duy trì tính nhất quán của tên riêng, địa danh và thuật ngữ xuyên
suốt toàn bộ tác phẩm, sử dụng RAG để tra cứu Character Glossary đã tích luỹ.

NĂNG LỰC: Bạn hiểu nguyên tắc giữ nguyên/phiên âm tên riêng trong dịch thuật
Trung–Việt (ví dụ: tên phương Tây giữ nguyên dạng gốc, không phiên âm Hán
Việt). Dữ liệu bạn được phép dùng: Character Glossary truy xuất từ ChromaDB
tương ứng với chương đang xử lý — đây là NGUỒN DUY NHẤT được phép dùng để xác
định cách viết chuẩn.

NGUYÊN TẮC:
- Cấm tuyệt đối tự sáng tạo cách viết mới cho bất kỳ tên riêng/thuật ngữ nào
  đã tồn tại trong glossary — bắt buộc dùng đúng canonical_form đã lưu.
- Với thuật ngữ hoàn toàn mới (chưa có trong glossary): không được tự ý
  chuẩn hoá — chỉ trích xuất và đề xuất dưới dạng new_entry_candidate kèm
  confidence_score, chờ xác nhận từ con người.
- Mọi quyết định phải truy nguyên được về một nguồn dữ liệu cụ thể trong
  glossary, không có ngoại lệ.

NHIỆM VỤ:
- Nhận văn bản chương hiện tại cùng glossary context truy xuất từ RAG.
- Rà soát toàn bộ tên riêng, địa danh, thuật ngữ đặc thù xuất hiện trong văn
  bản.
- Áp dụng canonical_form đã có trong glossary cho các thuật ngữ đã biết.
- Phát hiện và đề xuất (không tự áp dụng) đối với thuật ngữ mới.

TƯ DUY: quét toàn bộ văn bản tìm mọi tên riêng/địa danh/thuật ngữ đặc thù;
với mỗi thuật ngữ, truy vấn xem đã có trong glossary_context chưa; nếu có,
thay thế/xác nhận theo canonical_form; nếu không có, chỉ đánh dấu ứng viên
mới; không suy diễn thêm ngoài phạm vi văn bản và glossary được cung cấp.

PHONG CÁCH: Output JSON, field tiếng Anh, giá trị text tiếng Việt giữ nguyên
gốc. Không thêm bình luận hay giải thích lý do.
"""


class AppliedTerm(BaseModel):
    original: str
    canonical_form: str


class NewEntryCandidate(BaseModel):
    term: str
    # Ghim CÙNG Literal với GlossaryEntry.entity_type — nếu để str tự do,
    # Gemini structured output sẽ tự chọn nhãn hợp lý hơn theo góc nhìn của
    # nó (vd. "organization" cho tên môn phái/tông môn) nhưng KHÔNG khớp 3
    # loại glossary thực sự hỗ trợ, khiến approve_new_entries() (đúng chức
    # năng) âm thầm loại bỏ candidate đó — xác nhận có THẬT khi test live
    # (2026-09-09): "Huyết Nguyệt Tông" (một tông môn) bị Gemini gán
    # entity_type="organization" và bị bỏ qua hoàn toàn. Ép Literal ở đây bắt
    # Gemini phải chọn 1 trong 3 giá trị hợp lệ ngay từ schema (JSON mode tôn
    # trọng enum/Literal của pydantic) — khớp đúng ví dụ trong spec Section
    # 6.2, nơi "Huyết Nguyệt Tông" được gán entity_type="term".
    entity_type: Literal["character", "place", "term"]
    confidence_score: float


class BetaOutput(BaseModel):
    corrected_text: str
    applied_terms: list[AppliedTerm]
    new_entry_candidates: list[NewEntryCandidate]


def _build_user_content(chapter_text: str, glossary_context: list[dict]) -> str:
    context_lines = "\n".join(
        f"- {g.get('original_term')} -> {g.get('canonical_form')} ({g.get('entity_type')})"
        for g in glossary_context
    ) or "(glossary hiện đang trống — chưa có entry nào được tích luỹ)"
    return f"GLOSSARY CONTEXT:\n{context_lines}\n\nVĂN BẢN CHƯƠNG:\n{chapter_text}"


def run_beta(chapter_text: str, chapter_number: int = 0) -> dict:
    """Áp dụng glossary cho 1 chương, trả về dict {corrected_text,
    applied_terms, new_entry_candidates}.

    new_entry_candidates chỉ là ĐỀ XUẤT — KHÔNG tự động ghi vào glossary ở
    đây (đúng theo nguyên tắc "chờ xác nhận từ con người" trong system
    prompt). Dùng approve_new_entries() bên dưới sau khi người dùng xác
    nhận."""
    glossary_context = query_glossary(chapter_text)
    user_content = _build_user_content(chapter_text, glossary_context)
    result: BetaOutput = call_structured(SYSTEM_PROMPT, user_content, BetaOutput)
    return result.model_dump()


def approve_new_entries(candidates: list[dict], chapter_number: int | None = None) -> None:
    """Ghi các new_entry_candidates đã được con người xác nhận vào glossary,
    để các chương sau truy xuất được. entity_type phải là 1 trong
    "character"/"place"/"term" (theo GlossaryEntry) — candidate nào không
    khớp sẽ bị bỏ qua thay vì làm hỏng cả glossary.

    chapter_number: áp dụng cho MỌI candidate nếu candidate đó không tự mang
    key "chapter_number" riêng — cho phép gọi 1 lần với danh sách gộp từ
    NHIỀU chương/file khác nhau (mỗi candidate tự nhớ chương gốc của nó, xem
    panel "Duyệt Glossary" trong auto_tts.py) hoặc gọi kiểu cũ (1 chương, 1
    chapter_number chung — vẫn tương thích ngược)."""
    valid_types = {"character", "place", "term"}
    for c in candidates:
        if c.get("entity_type") not in valid_types:
            continue
        add_entry(GlossaryEntry(
            original_term=c["term"],
            entity_type=c["entity_type"],
            canonical_form=c.get("canonical_form", c["term"]),
            first_seen_chapter=c.get("chapter_number", chapter_number),
        ))
