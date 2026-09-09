"""Schema state dùng chung xuyên suốt LangGraph (graph.py)."""

from typing import Optional, TypedDict


class VoxDirectorState(TypedDict):
    raw_text: str
    chapters: list[dict]  # output của Alpha
    current_chapter_index: int
    glossary_context: list[dict]  # truy xuất từ ChromaDB cho chương hiện tại
    corrected_text: str  # output của Beta
    normalized_text: str  # output của text_normalizer.py (existing)
    split_chunks: list[str]  # output của text_splitter.py (existing)
    tagged_segments: list[dict]  # output của Gamma (narration/dialogue + speaker_id — KHÔNG có emotion)
    rendered_audio_path: str
    final_video_path: str
    qa_report: Optional[dict]  # output của Delta
