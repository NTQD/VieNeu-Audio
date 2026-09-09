"""Agent Delta live test: faster-whisper that (khong can API key) +
summarize_qa_report qua Gemini that. Doc key tu file tam ngoai repo, KHONG
bao gio in lai key, xoa file tam sau khi dung xong (do nguoi goi).

Chay: python scratch_check/test_agent_delta_live.py
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

from voxdirector.agents.delta_qa import verify_audio_quality, summarize_qa_report

RTF_TEXT = (
    "Hôm nay là một ngày đẹp trời, ánh nắng chan hòa khắp phố phường Hà Nội. "
    "Mọi người đi lại tấp nập, trẻ em nô đùa trong công viên, còn người lớn thì "
    "ngồi uống cà phê và trò chuyện vui vẻ bên vỉa hè, tạo nên một khung cảnh vô "
    "cùng yên bình và đáng nhớ giữa lòng thành phố này."
)


def main():
    print("== verify_audio_quality() trên audio thật (đã có kết quả từ trước, chạy lại để có qa_report) ==")
    result = verify_audio_quality("scratch_check/out/rtf_test.wav", RTF_TEXT)
    qa_report = {
        "word_error_rate": round(result["word_error_rate"], 2),
        "passed": result["passed"],
        "flagged_segments": [],
    }
    print(f"qa_report: {qa_report}")

    print("\n== summarize_qa_report() qua Gemini thật ==")
    try:
        summary = summarize_qa_report(qa_report)
    except Exception as e:
        key = os.environ.get("GEMINI_API_KEY", "")
        msg = str(e).replace(key, "[REDACTED_API_KEY]") if key else str(e)
        print(f"LỖI: {type(e).__name__}: {msg}")
        return
    print(f"Tóm tắt: {summary!r}")


if __name__ == "__main__":
    main()
