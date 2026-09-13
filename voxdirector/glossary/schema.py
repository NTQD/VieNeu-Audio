"""Schema cho Character/Terminology Glossary dùng bởi Agent Beta."""

from typing import Literal, Optional

from pydantic import BaseModel


class GlossaryEntry(BaseModel):
    original_term: str
    entity_type: Literal["character", "place", "term"]
    canonical_form: str
    pronunciation_note: Optional[str] = None
    # Optional (khong phai int bat buoc) - xac nhan co THAT qua bug 500 khi
    # test song POST /api/glossary/approve (Phase 0, Section 5a): candidate tu
    # frontend khong mang chapter_number (xem NewTermCandidate trong
    # frontend/src/lib/types.ts), approve_new_entries() mac dinh None cho
    # tham so nay - truoc ban sua nay field bat buoc int khien Pydantic raise
    # ValidationError, lam approve_new_entries() LUON THAT BAI khi khong co
    # chapter_number, tuc LA MOI LAN goi tu UI hien tai.
    first_seen_chapter: Optional[int] = None
