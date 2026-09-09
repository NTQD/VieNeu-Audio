"""Schema cho Character/Terminology Glossary dùng bởi Agent Beta."""

from typing import Literal, Optional

from pydantic import BaseModel


class GlossaryEntry(BaseModel):
    original_term: str
    entity_type: Literal["character", "place", "term"]
    canonical_form: str
    pronunciation_note: Optional[str] = None
    first_seen_chapter: int
