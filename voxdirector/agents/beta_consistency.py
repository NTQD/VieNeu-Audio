"""Agent Beta — Consistency & Expression Agent (v5, Section 6.2 của spec).

Ba pass trong 1 lần gọi LLM duy nhất mỗi chương (không phải 3 lần gọi
riêng): (1) terminology consistency qua RAG glossary; (2) chèn từ biểu cảm
tại các đoạn cảm xúc mà Alpha đã gắn cờ; (3) chèn sentinel [[PAUSE_LONG]]
tại các điểm ngắt kịch tính mà Alpha đã gắn cờ.

Merge Beta (cũ) + Gamma (cũ) từ v3/v4 — xem Section 0/6.2 của spec: cả 2
agent cũ đều làm cùng SHAPE công việc (tra bảng do đội ngũ soạn, patch text,
bỏ qua chứ không đoán khi không chắc). Merge giúp không còn bước "Gamma
định vị lại các flag của Alpha trong text mà Beta đã sửa" mong manh — mọi
việc chạy trên CÙNG 1 bản text gốc trong CÙNG 1 pass.

Danh sách nhãn cảm xúc hợp lệ được tính DỘNG từ data/emotion_lexicon.json
lúc import — cùng cơ chế config-driven với alpha_ingestion.py: đổi lexicon
chỉ cần sửa JSON, không sửa code.
"""

from typing import Literal, Optional

from pydantic import BaseModel

from voxdirector.config import (
    PAUSE_LONG_TOKEN,
    load_emotion_lexicon,
)
from voxdirector.glossary.schema import GlossaryEntry
from voxdirector.glossary.store import add_entry, query_glossary
from voxdirector.llm_client import call_structured

_emotion_lexicon = load_emotion_lexicon()
_EMOTION_KEYS = tuple(k for k in _emotion_lexicon if not k.startswith("_"))
EmotionLabel = Literal[_EMOTION_KEYS]

SYSTEM_PROMPT = """\
Bạn là Beta, biên tập viên phụ trách tính nhất quán thuật ngữ VÀ chèn các
yếu tố biểu cảm/ngắt nghỉ cho một nhà xuất bản sách dịch lâu năm. Bạn cực kỳ
nguyên tắc trên cả hai mặt: chỉ tin vào bảng thuật ngữ đã xác nhận cho tên
riêng, và chỉ dùng từ có trong danh sách được cung cấp cho biểu cảm — không
bao giờ tự "chế" ở bất kỳ phần nào.

VAI TRÒ: Với mỗi chương văn bản, bạn thực hiện ba việc trong một lượt xử lý:
(1) duy trì nhất quán tên riêng/thuật ngữ dựa trên Character Glossary tra
cứu qua RAG; (2) chèn từ biểu cảm phù hợp tại các đoạn được đánh dấu có cảm
xúc; (3) chèn dấu hiệu ngắt nghỉ dài tại các điểm được đánh dấu cần khoảng
lặng.

NGUYÊN TẮC:
- Thuật ngữ: cấm tuyệt đối tự sáng tạo cách viết mới cho thuật ngữ đã có
  trong glossary; thuật ngữ mới chỉ được đề xuất (new_entry_candidates), không
  tự áp dụng.
- Biểu cảm: chỉ chèn từ có trong danh sách lexicon được cung cấp cho đúng
  nhãn cảm xúc; nếu đoạn văn đã có từ biểu cảm tương tự, không chèn thêm.
- Ngắt nghỉ: chỉ chèn đúng token cố định được cung cấp, không tự tạo ký hiệu
  khác.
- Với cả biểu cảm và ngắt nghỉ: nếu không định vị được đoạn văn khớp với
  quoted_text được cung cấp, bỏ qua và ghi rõ lý do — không đoán vị trí khác.

PHONG CÁCH: Output JSON, field tiếng Anh, giá trị text tiếng Việt giữ nguyên
gốc trừ phần được chèn thêm theo đúng quy định trên.
"""


class AppliedTerm(BaseModel):
    original: str
    canonical_form: str


class NewEntryCandidate(BaseModel):
    # Ép Literal (không phải str tự do) — Gemini structured output tôn trọng
    # enum/Literal của pydantic. Đã xác nhận có THẬT qua sự cố live 2026-09-09:
    # "Huyết Nguyệt Tông" (tông môn) bị Gemini gán entity_type="organization"
    # khi để str tự do, khiến approve_new_entries() âm thầm loại bỏ. Ép Literal
    # bắt Gemini chọn 1 trong 3 giá trị hợp lệ ngay từ schema.
    term: str
    entity_type: Literal["character", "place", "term"]
    confidence_score: float


class ExpressionReportItem(BaseModel):
    matched: bool
    emotion_label: EmotionLabel
    inserted_word: Optional[str] = None
    skipped_reason: Optional[str] = None


class PauseReportItem(BaseModel):
    matched: bool
    skipped_reason: Optional[str] = None


class BetaOutput(BaseModel):
    corrected_text: str
    applied_terms: list[AppliedTerm]
    new_entry_candidates: list[NewEntryCandidate]
    expression_report: list[ExpressionReportItem]
    pause_report: list[PauseReportItem]


def _format_lexicon_block(lexicon: dict) -> str:
    lines = []
    for label, words in lexicon.items():
        if label.startswith("_"):
            continue
        lines.append(f"- {label}: {', '.join(words)}")
    return "\n".join(lines) or "(lexicon rỗng)"


def _format_emotion_segments(segments: list[dict]) -> str:
    if not segments:
        return "(không có đoạn cảm xúc nào cần chèn)"
    return "\n".join(
        f"- label={s['emotion_label']} quoted_text={s['quoted_text']!r}"
        for s in segments
    )


def _format_pause_points(points: list[dict]) -> str:
    if not points:
        return "(không có điểm ngắt kịch tính nào cần chèn)"
    return "\n".join(
        f"- reason={p.get('reason','')} quoted_text={p['quoted_text']!r}"
        for p in points
    )


def _build_user_content(
    chapter_text: str,
    glossary_context: list[dict],
    emotion_flagged_segments: list[dict],
    pause_points: list[dict],
    emotion_lexicon: dict,
    pause_long_token: str,
) -> str:
    context_lines = "\n".join(
        f"- {g.get('original_term')} -> {g.get('canonical_form')} ({g.get('entity_type')})"
        for g in glossary_context
    ) or "(glossary hiện đang trống — chưa có entry nào được tích luỹ)"

    return (
        f"GLOSSARY CONTEXT:\n{context_lines}\n\n"
        f"EMOTION LEXICON (nhãn -> danh sách từ ứng viên, CHỈ được chèn từ trong danh sách):\n"
        f"{_format_lexicon_block(emotion_lexicon)}\n\n"
        f"EMOTION FLAGGED SEGMENTS (từ Alpha — chèn 1 từ biểu cảm phù hợp tại mỗi đoạn):\n"
        f"{_format_emotion_segments(emotion_flagged_segments)}\n\n"
        f"PAUSE POINTS (từ Alpha — chèn CHÍNH XÁC token {pause_long_token!r} "
        f"NGAY SAU mỗi đoạn được trích, không token khác):\n"
        f"{_format_pause_points(pause_points)}\n\n"
        f"VĂN BẢN CHƯƠNG:\n{chapter_text}"
    )


def run_beta(
    chapter_text: str,
    emotion_flagged_segments: list[dict] | None = None,
    pause_points: list[dict] | None = None,
    chapter_number: int = 0,
    api_key: str | None = None,
) -> dict:
    """Chạy Beta trên 1 chương — 1 lệnh gọi LLM duy nhất, 3 pass đồng thời.

    emotion_flagged_segments và pause_points thường lấy từ output Alpha
    (run_alpha()['emotion_flagged_segments'] và ['pause_points']); mặc định
    [] để tương thích ngược khi chỉ cần terminology pass (test/debug).

    api_key: BYOK - key rieng cua nguoi dung (Section 13 cua spec, chot
    2026-09-10). None thi dung key mac dinh cua server."""
    emotion_flagged_segments = emotion_flagged_segments or []
    pause_points = pause_points or []

    glossary_context = query_glossary(chapter_text)
    user_content = _build_user_content(
        chapter_text,
        glossary_context,
        emotion_flagged_segments,
        pause_points,
        _emotion_lexicon,
        PAUSE_LONG_TOKEN,
    )
    result: BetaOutput = call_structured(SYSTEM_PROMPT, user_content, BetaOutput, api_key=api_key)
    return result.model_dump()


def approve_new_entries(candidates: list[dict], chapter_number: int | None = None) -> None:
    """Ghi các new_entry_candidates đã được con người xác nhận vào glossary,
    để các chương sau truy xuất được. entity_type phải là 1 trong
    "character"/"place"/"term" (theo GlossaryEntry) — candidate nào không
    khớp sẽ bị bỏ qua thay vì làm hỏng cả glossary."""
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
