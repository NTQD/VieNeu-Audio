"""Tien ich xu ly text DUNG CHUNG giua nhieu Agent - tach ra khoi
voxdirector/agents/alpha_ingestion.py (Phase 2 cua
ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md) khi Beta (Phase 3, muc 11)
can lai CHINH XAC cung 1 logic windowing/chuan hoa/loc item - tranh viet
trung lan thu 2 (va backend/app/main.py cung co 1 ban gan giong y het
truoc do, gop lai lam MOT nguon duy nhat).
"""

import re
from typing import Optional

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
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


_PARAGRAPH_BREAK_SNAP_RADIUS = 500


def snap_to_paragraph_break(text: str, pos: int) -> int:
    """Dich pos ve diem ngat doan (\\n\\n) gan nhat trong ban kinh
    _PARAGRAPH_BREAK_SNAP_RADIUS ky tu, uu tien ben nao gan hon - tranh cat 1
    cua so/chunk giua chung 1 cau/1 tieu de chuong, co the khien LLM hieu
    sai ranh gioi ngay tai diem cat. Neu khong tim thay "\\n\\n" nao trong
    ban kinh, thu "\\n" don; neu van khong co, giu nguyen pos (cat cung, chi
    xay ra voi van ban khong co doan xuong dong ro rang nao gan do)."""
    lo = max(0, pos - _PARAGRAPH_BREAK_SNAP_RADIUS)
    hi = min(len(text), pos + _PARAGRAPH_BREAK_SNAP_RADIUS)

    def _closest(token: str) -> Optional[int]:
        before = text.rfind(token, lo, pos)
        after = text.find(token, pos, hi)
        candidates = []
        if before != -1:
            candidates.append((pos - (before + len(token)), before + len(token)))
        if after != -1:
            candidates.append((after - pos, after))
        if not candidates:
            return None
        return min(candidates, key=lambda t: t[0])[1]

    # KHONG dung "or" de noi chuoi fallback - _closest() co the tra ve 0 (1
    # vi tri hop le that su, vd. diem ngat doan nam dung dau ban kinh tim
    # kiem), "0 or X" se sai lam roi qua nhanh X vi Python coi 0 la falsy.
    double_break = _closest("\n\n")
    if double_break is not None:
        return double_break
    single_break = _closest("\n")
    if single_break is not None:
        return single_break
    return pos


def split_into_windows(text: str, window_chars: int, overlap_chars: int) -> list[tuple[int, int]]:
    """Chia text thanh danh sach (start, end) chong lan overlap_chars ky tu
    giua 2 cua so lien tiep. text_len <= window_chars -> tra ve DUNG 1 cua
    so bao trum toan bo van ban (khong windowing gi ca).

    overlap_chars=0 -> chia THANH TUNG MANH KHONG CHONG LAN (dung boi Beta,
    Phase 3 muc 11 - khac Alpha, Beta khong can ngu canh chong lan de doi
    chieu ranh gioi, chi can khong cat mot cau lam doi)."""
    text_len = len(text)
    if text_len <= window_chars:
        return [(0, text_len)]

    windows = []
    start = 0
    while True:
        end = min(start + window_chars, text_len)
        if end < text_len:
            end = snap_to_paragraph_break(text, end)
        windows.append((start, end))
        if end >= text_len:
            break
        next_start = end - overlap_chars
        if next_start <= start:  # phong ngua cau hinh sai (overlap >= window) gay vong lap vo han
            next_start = end
        start = next_start
    return windows


def items_for_span(items: list[dict], span_text: str) -> list[dict]:
    """Loc emotion_flagged_segments/pause_points (dict, key 'quoted_text')
    ve dung nhung item co quoted_text nam trong span_text - span_text co
    the la 1 chuong (orchestrator.py) HOAC 1 chunk nho hon trong chuong
    (Phase 3, beta_consistency.py loc theo tung chunk truoc khi goi Beta)."""
    normalized_span = normalize_ws(span_text)
    return [item for item in items if normalize_ws(item["quoted_text"]) in normalized_span]


def dedupe_by_key(items, key_fn, score_fn=lambda item: item.confidence_score):
    """Loai item TRUNG LAP theo key_fn(item), giu ban co score_fn(item) cao
    hon - tong quat hoa alpha_ingestion.py ban cu _dedupe_by_quoted_text
    (key = quoted_text da chuan hoa) de Beta (Phase 3) dung lai duoc voi key
    khac (vd. .term cho new_entry_candidates) thay vi viet lai ham gan
    giong het."""
    best = {}
    for item in items:
        key = key_fn(item)
        existing = best.get(key)
        if existing is None or score_fn(item) > score_fn(existing):
            best[key] = item
    return list(best.values())
