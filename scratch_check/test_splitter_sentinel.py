"""Step 6 - test text_splitter voi sentinel [[PAUSE_LONG]] giua chunk.

Chay: python scratch_check/test_splitter_sentinel.py
"""
import os, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.text_splitter import split_text_with_boundaries, split_text_for_tts

# Case 1: sentinel giua chunk (chua den 250 tu) -> phai ep ranh gioi
SHORT_WITH_SENTINEL = (
    "Cau mot rat ngan. Cau hai cung ngan. [[PAUSE_LONG]] "
    "Cau ba sau khi ngat. Cau bon nua."
)

# Case 2: khong co sentinel -> hanh vi cu (chi word-count)
NO_SENTINEL = " ".join([f"Cau so {i}." for i in range(50)])

# Case 3: sentinel giua doan dai (>250 tu tren tung phia) -> co CA "pause_long"
# lan "default" boundaries
LONG_WITH_SENTINEL = " ".join([f"Cau {i}." for i in range(300)]) + " [[PAUSE_LONG]] " + " ".join([f"Cau {i}." for i in range(300, 600)])


def run(label, text, expected_chunks_min, expected_flags_contain):
    chunks, flags = split_text_with_boundaries(text, max_words=250)
    print(f"\n--- {label} ---")
    print(f"chunks={len(chunks)} flags={flags}")
    for i, c in enumerate(chunks):
        preview = c[:60] + ("..." if len(c) > 60 else "")
        print(f"  [{i}] ({len(c.split())} tu) {preview!r}")
    checks = [
        (f"co it nhat {expected_chunks_min} chunks", len(chunks) >= expected_chunks_min),
        (f"khong chunk nao con chua sentinel", not any("[[PAUSE_LONG]]" in c for c in chunks)),
        (f"flags chua {expected_flags_contain!r}", expected_flags_contain in flags if flags else expected_flags_contain is None),
    ]
    for lbl, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {lbl}")


run("Case 1: sentinel ep ranh gioi trong doan ngan", SHORT_WITH_SENTINEL, 2, "pause_long")
run("Case 2: khong sentinel -> chi 1 chunk (van chua qua 250 tu)", NO_SENTINEL, 1, None)
run("Case 3: sentinel + word-count", LONG_WITH_SENTINEL, 3, "pause_long")

# Backward-compat check
plain = split_text_for_tts(SHORT_WITH_SENTINEL, max_words=250)
print(f"\n--- Backward compat split_text_for_tts ---")
print(f"co {len(plain)} chunk, khong chua sentinel: {not any('[[PAUSE_LONG]]' in c for c in plain)}")
