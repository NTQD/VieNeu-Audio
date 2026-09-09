"""Step: Agent Beta live test - Gemini API that + ChromaDB that (thu muc tam
rieng, KHONG dung glossary that cua du an). Doc key tu file tam ngoai repo,
KHONG bao gio in lai key, xoa file tam sau khi dung xong (do nguoi goi).

Chay: python scratch_check/test_agent_beta_live.py
"""
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

# Thu muc ChromaDB TAM, cach ly hoan toan voi glossary that cua du an.
os.environ["VOXDIRECTOR_CHROMA_DIR"] = tempfile.mkdtemp(prefix="voxdirector_beta_live_")

KEY_FILE = (
    r"C:\Users\admin\AppData\Local\Temp\claude\E--tool-audio-VieNeu-TTS--"
    r"claude-worktrees-tts-colab-gpu-performance-5c6608\0a628a73-c803-433c-"
    r"b507-edb2c0f40485\scratchpad\gemini_key.txt"
)
with open(KEY_FILE, "r", encoding="utf-8") as f:
    os.environ["GEMINI_API_KEY"] = f.read().strip()

from voxdirector.glossary.schema import GlossaryEntry
from voxdirector.glossary.store import seed_entries, query_glossary
from voxdirector.agents.beta_consistency import run_beta, approve_new_entries

CHAPTER_TEXT = (
    "Lý Phong đứng trước cổng thành, ánh mắt kiên định. Hắn vừa nhận được tin "
    "từ trưởng lão Huyết Nguyệt Tông rằng có một trận chiến lớn sắp xảy ra. "
    "\"Lý Phong, ngươi phải cẩn thận,\" một giọng nói vang lên từ phía sau."
)


def main():
    print("== Seeding glossary (1 entry đã biết: 'Lý Phong') ==")
    seed_entries([
        GlossaryEntry(original_term="Lý Phong", entity_type="character",
                      canonical_form="Lý Phong", first_seen_chapter=1),
    ])

    print("\n== run_beta() trên chương có 1 term đã biết + 1 term hoàn toàn mới ==")
    try:
        result = run_beta(CHAPTER_TEXT, chapter_number=2)
    except Exception as e:
        key = os.environ.get("GEMINI_API_KEY", "")
        msg = str(e).replace(key, "[REDACTED_API_KEY]") if key else str(e)
        print(f"LOI: {type(e).__name__}: {msg}")
        return

    print(f"corrected_text: {result['corrected_text']!r}")
    print(f"applied_terms: {result['applied_terms']}")
    print(f"new_entry_candidates: {result['new_entry_candidates']}")

    known_applied = any(t.get("original") == "Lý Phong" or t.get("canonical_form") == "Lý Phong"
                         for t in result["applied_terms"])
    print(f"\n-> 'Lý Phong' (đã biết) được áp dụng đúng: {known_applied}")

    new_terms = [c["term"] for c in result["new_entry_candidates"]]
    print(f"-> Thuật ngữ mới phát hiện (chưa có trong glossary): {new_terms}")

    if result["new_entry_candidates"]:
        print("\n== Duyệt new_entry_candidates vào glossary (approve_new_entries) ==")
        for c in result["new_entry_candidates"]:
            c["chapter_number"] = 2
        approve_new_entries(result["new_entry_candidates"])
        print("Đã ghi. Query lại glossary để xác nhận:")
        entries = query_glossary("Huyết Nguyệt Tông", top_k=10)
        for e in entries:
            print(" ", e)


if __name__ == "__main__":
    main()
