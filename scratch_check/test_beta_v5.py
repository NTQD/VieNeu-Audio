"""Build order Step 5 - test Beta v5 (merged) tren 1 chuong that voi flag
tu Alpha. Goi Gemini THAT.

Chay: python scratch_check/test_beta_v5.py
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHAPTER = """Lý Phong dừng bước trước cổng Hắc Vân Môn, tay nắm chặt thanh kiếm bên hông.
Gã đã lang bạt giang hồ nhiều năm, chưa từng thấy môn phái nào u ám như thế này.
- Ha ha ha! Ngươi tưởng một mình có thể phá được trận pháp của bổn môn sao?
Tiếng cười lớn vang vọng khắp đại sảnh, đầy vẻ ngạo mạn và khinh thường.
Đêm đó, cả tòa sơn trang chìm vào im lặng tuyệt đối, chỉ còn tiếng gió rít qua từng khe đá."""

EMOTION_FLAGS = [
    {
        "quoted_text": "- Ha ha ha! Ngươi tưởng một mình có thể phá được trận pháp của bổn môn sao?",
        "emotion_label": "cuoi",
        "confidence_score": 0.95,
    }
]

PAUSE_POINTS = [
    {
        "quoted_text": "Đêm đó, cả tòa sơn trang chìm vào im lặng tuyệt đối, chỉ còn tiếng gió rít qua từng khe đá.",
        "reason": "Chuyển cảnh + im lặng miêu tả rõ",
        "confidence_score": 0.9,
    }
]


def main():
    # Vong tranh su co protobuf version mismatch pre-existing cua chromadb
    # trong .venv nay: chuong dau tien luon dung glossary rong (test/debug
    # doc lap), boc query_glossary = lambda -> [] la trang thai binh thuong
    # duoc chinh docstring cua store.py xac nhan an toan.
    import voxdirector.agents.beta_consistency as beta_mod
    beta_mod.query_glossary = lambda *a, **kw: []

    from voxdirector.agents.beta_consistency import run_beta
    from voxdirector.config import PAUSE_LONG_TOKEN

    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print("LOI: chua co GEMINI_API_KEY."); sys.exit(1)

    print("Dang goi Agent Beta...\n")
    result = run_beta(CHAPTER, EMOTION_FLAGS, PAUSE_POINTS, chapter_number=1)

    print("=== corrected_text ===")
    print(result["corrected_text"])
    print()

    print("=== applied_terms ===", result["applied_terms"])
    print("=== new_entry_candidates ===", result["new_entry_candidates"])
    print("=== expression_report ===", result["expression_report"])
    print("=== pause_report ===", result["pause_report"])

    print("\n=== KIEM TRA ===")
    checks = [
        (f"corrected_text co chua {PAUSE_LONG_TOKEN}", PAUSE_LONG_TOKEN in result["corrected_text"]),
        ("expression_report co it nhat 1 entry matched=True",
         any(e["matched"] for e in result["expression_report"])),
        ("pause_report co it nhat 1 entry matched=True",
         any(p["matched"] for p in result["pause_report"])),
        ("new_entry_candidates co Hac Van Mon (tong mon = term)",
         any("Hắc Vân Môn" in c.get("term", "") for c in result["new_entry_candidates"])),
    ]
    for label, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {label}")


if __name__ == "__main__":
    main()
