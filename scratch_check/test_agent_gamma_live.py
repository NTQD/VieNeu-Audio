"""Agent Gamma live test - Gemini API that. Doc key tu file tam ngoai repo,
KHONG bao gio in lai key, xoa file tam sau khi dung xong (do nguoi goi).

Chay: python scratch_check/test_agent_gamma_live.py
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

KEY_FILE = (
    r"C:\Users\admin\AppData\Local\Temp\claude\E--tool-audio-VieNeu-TTS--"
    r"claude-worktrees-tts-colab-gpu-performance-5c6608\0a628a73-c803-433c-"
    r"b507-edb2c0f40485\scratchpad\gemini_key.txt"
)
with open(KEY_FILE, "r", encoding="utf-8") as f:
    os.environ["GEMINI_API_KEY"] = f.read().strip()

from voxdirector.agents.gamma_prosody import tag_segments

# Doan van co ca loi dan truyen VA loi thoai (2 nhan vat khac nhau), cau
# thoai co dong tu tuong thuat ro rang de kiem tra kha nang gan speaker_id.
TEXT_CHUNK = (
    "Trời đã tối hẳn, gió lạnh thổi qua khu rừng vắng. Lý Phong dừng bước, "
    "nhíu mày nhìn về phía xa. \"Có ai đó đang theo dõi chúng ta,\" hắn nói "
    "nhỏ, giọng đầy cảnh giác. Tiểu Yến giật mình, nắm chặt tay áo Lý Phong. "
    "\"Chúng ta nên rời khỏi đây ngay,\" nàng thì thầm đáp lại."
)


def main():
    print(f"Đoạn văn kiểm tra ({len(TEXT_CHUNK)} ký tự):\n{TEXT_CHUNK}\n")
    try:
        segments = tag_segments(TEXT_CHUNK)
    except Exception as e:
        key = os.environ.get("GEMINI_API_KEY", "")
        msg = str(e).replace(key, "[REDACTED_API_KEY]") if key else str(e)
        print(f"LỖI: {type(e).__name__}: {msg}")
        return

    print(f"Số đoạn (segments) phát hiện: {len(segments)}\n")
    for i, s in enumerate(segments):
        print(f"  [{i}] type={s['segment_type']:<10} speaker_id={s['speaker_id']!r:<15} "
              f"confidence={s['confidence_score']:.2f}")
        print(f"       text: {s['text']!r}")

    n_narration = sum(1 for s in segments if s["segment_type"] == "narration")
    n_dialogue = sum(1 for s in segments if s["segment_type"] == "dialogue")
    speakers = {s["speaker_id"] for s in segments if s["speaker_id"]}
    print(f"\n-> {n_narration} đoạn dẫn truyện, {n_dialogue} đoạn thoại, "
          f"{len(speakers)} speaker khác nhau: {speakers}")
    print("-> Mọi speaker_id/segment_type có hợp lệ theo schema (Literal) không: đã được")
    print("   Pydantic tự validate lúc parse - nếu code chạy tới đây tức là hợp lệ.")


if __name__ == "__main__":
    main()
