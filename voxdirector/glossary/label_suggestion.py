"""Goi y entity_type (character/place/term) cho 1 thuat ngu MOI nguoi dung tu
go vao Glossary manager (khong phai do Beta tu phat hien - nhung candidate DO
da luon mang entity_type hop le vi Gemini bi ep Literal, xem NewEntryCandidate
trong voxdirector/agents/beta_consistency.py). Truong hop can goi y CHI xay
ra khi nguoi dung THEM entry moi thu cong qua UI ma chua chon loai.

HEURISTIC THEO TU KHOA - KHONG dung Gemini/embedding (tranh them 1 lan goi
LLM tra phi + do tre chi cho 1 goi y phu, va van hoat dong duoc khi khong co
GEMINI_API_KEY). Tuned so cho van phong kiem hiep/tien hiep tieng Viet (dung
the loai voi cac vi du co san trong data/glossary_seed.json) - GIA TRI TAM
THOI, CHUA CHOT, danh sach tu khoa co the/nen duoc mo rong khi gap truong hop
sai - chi la goi y de nguoi dung xac nhan/sua, khong phai phan loai bat buoc
dung tuyet doi."""

from typing import Literal

EntitySuggestion = Literal["character", "place", "term"]

# Hau to/tu khoa thuong gap trong dia danh hoac to chuc/mon phai (mon phai
# duoc xep vao "place" - gan voi cach ChromaDB glossary hien tai chi co 3
# loai, khong co "organization" rieng, xem ghi chu trong voxdirector/glossary/schema.py).
_PLACE_KEYWORDS = [
    "sơn", "cốc", "thành", "quốc", "cung", "điện", "lâu", "các",
    "trang", "đảo", "hồ", "giang", "phủ", "trấn", "quan",
    "tông", "môn", "phái", "bang", "hội", "cốc phủ",
]

# Hau to/tu khoa thuong gap trong thuat ngu vo cong/vat pham/khai niem.
_TERM_KEYWORDS = [
    "kiếm", "đao", "quyền", "công", "pháp", "quyết", "kinh", "đan",
    "trận", "chú", "thuật", "kỹ", "bí kíp", "linh khí", "nội lực",
]


def suggest_entity_type(term: str) -> EntitySuggestion:
    """Goi y entity_type cho 1 term - so khop KHONG PHAN BIET HOA/THUONG
    theo tu khoa cuoi/trong cum tu (khong yeu cau khop CHINH XAC 1 tu rieng
    le, vi ten rieng tieng Viet thuong la cum nhieu tu, vd "Thanh Van Son").
    Uu tien place truoc term (mot cum vua co "Sơn" vua co "Kiếm" - vd ten dia
    danh dat theo vu khi - nhieu kha nang la dia danh hon). Khong khop gi ca
    -> "character" (mac dinh an toan nhat: da so thuat ngu moi Beta/nguoi
    dung phat hien la ten nguoi/nhan vat, xem cac vi du co san trong
    data/glossary_seed.json)."""
    normalized = term.strip().lower()
    if not normalized:
        return "character"

    if any(kw in normalized for kw in _PLACE_KEYWORDS):
        return "place"
    if any(kw in normalized for kw in _TERM_KEYWORDS):
        return "term"
    return "character"
