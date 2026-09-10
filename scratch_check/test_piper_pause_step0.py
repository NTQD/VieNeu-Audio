"""Section 11 Step 0 - empirical test: does Piper's own training already
produce natural, distinguishable pausing at Vietnamese punctuation (comma,
period, question mark, exclamation mark, ellipsis) and at the dialogue-dash
line-start convention? Gate for whether Section 7.3 needs to be built at
all.

Chay: python scratch_check/test_piper_pause_step0.py
"""
import os
import sys
import wave

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VOICE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "piper_voices")
MODEL_PATH = os.path.join(VOICE_DIR, "vi_VN-vais1000-medium.onnx")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "piper_step0")
os.makedirs(OUT_DIR, exist_ok=True)

# Doan van kiem tra: co day du dau phay, cham, hoi, than, "..." va 1 dong
# thoai bat dau bang gach ngang (quy uoc tieng Viet).
TEST_TEXT = (
    "- Anh đi đâu đấy?\n"
    "Cô ấy hỏi, giọng đầy lo lắng. Trời đã tối. "
    "Anh có chắc không? Đừng làm vậy! "
    "Cô ấy níu tay anh lại..."
)


def main():
    from piper.voice import PiperVoice
    from piper.config import SynthesisConfig

    print("Dang tai voice (co bat include_alignments de do thoi gian tung phoneme that)...")
    voice = PiperVoice.load(MODEL_PATH, include_alignments=True)
    print(f"Sample rate: {voice.config.sample_rate}")

    print(f"\nVan ban kiem tra:\n{TEST_TEXT}\n")

    all_audio = bytearray()
    all_alignments = []  # list cua (phoneme, start_sample, end_sample) qua tat ca chunk
    total_samples = 0

    for chunk_idx, chunk in enumerate(voice.synthesize(TEST_TEXT, include_alignments=True)):
        audio_bytes = chunk.audio_int16_bytes
        all_audio.extend(audio_bytes)
        print(f"--- chunk {chunk_idx}: {len(chunk.phonemes)} phoneme, "
              f"{len(audio_bytes) // 2} sample ---")
        print(f"  phonemes: {chunk.phonemes}")
        if chunk.phoneme_alignments:
            for al in chunk.phoneme_alignments:
                all_alignments.append((chunk_idx, al.phoneme, al.num_samples))
        total_samples += len(audio_bytes) // 2

    # Luu file .wav day du de nguoi dung tu nghe doi chieu.
    out_wav = os.path.join(OUT_DIR, "step0_pause_test.wav")
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(voice.config.sample_rate)
        wf.writeframes(bytes(all_audio))
    print(f"\nDa luu: {out_wav} ({total_samples / voice.config.sample_rate:.2f}s)")

    if not all_alignments:
        print("\n[CANH BAO] Khong co du lieu alignment tu model nay - khong the do "
              "chinh xac thoi gian tung phoneme. Chi co file audio de nghe thu.")
        return

    sample_rate = voice.config.sample_rate

    print(f"\n=== Thoi luong (giay) cua tung phoneme dau/cuoi cau (bao gom dau cau) ===")
    print(f"(Danh sach TAT CA phoneme kem thoi luong, de doi chieu vi tri):")
    for chunk_idx, phoneme, num_samples in all_alignments:
        dur_s = num_samples / sample_rate
        marker = "  <== DAU CAU" if phoneme in {",", ".", "?", "!", "-"} else ""
        print(f"  chunk {chunk_idx}: phoneme={phoneme!r:8} duration={dur_s*1000:6.0f}ms{marker}")

    punct_durations = {}
    for chunk_idx, phoneme, num_samples in all_alignments:
        if phoneme in {",", ".", "?", "!", "-"}:
            punct_durations.setdefault(phoneme, []).append(num_samples / sample_rate)

    print("\n=== Tom tat thoi luong theo tung loai dau cau ===")
    for punct, durs in punct_durations.items():
        avg = sum(durs) / len(durs)
        print(f"  {punct!r}: {len(durs)} lan, trung binh {avg*1000:.0f}ms, "
              f"cac lan: {[f'{d*1000:.0f}ms' for d in durs]}")

    if "..." not in [p for _, p, _ in all_alignments]:
        print("\n[PHAT HIEN] '...' KHONG xuat hien nhu 1 phoneme rieng trong output cua "
              "phonemizer (da xac nhan qua voice.phonemize() truoc do) - nghia la Piper "
              "KHONG co co che nao de tao khoang lang dai hon rieng cho dau '...', vi ban "
              "than ky tu nay khong con ton tai trong chuoi phoneme dua vao model.")

    print("\n[PHAT HIEN] Dau gach ngang dau dong thoai ('- ...') CUNG bi phonemizer loai "
          "bo hoan toan (da xac nhan qua voice.phonemize() truoc do) - Piper khong co cach "
          "nao phan biet day la 1 dong thoai nhan vat moi, vi ky tu do khong con trong input "
          "dua vao model.")


if __name__ == "__main__":
    main()
