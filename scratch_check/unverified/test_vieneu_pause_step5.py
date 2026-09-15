"""Step 5 cua yeu cau doi engine (2026-09-11) - kiem tra thuc nghiem: VieNeu-TTS
tu no co tao ngat nghi tu nhien/phan biet duoc tai dau cau tieng Viet
(phay/cham/hoi/than/"..."/dau gach ngang dau dong thoai) hay khong - tuong
tu ve tinh than voi Step 0 cu cua Piper, de quyet dinh Section 7.2/7.3 co
con can thiet voi engine moi hay khong.

VieNeu-TTS KHONG expose phoneme alignment nhu Piper (kien truc khac hoan
toan - khong phai espeak-based phonemizer) - nen dung phuong phap khac,
ENGINE-AGNOSTIC: phan tich nang luong (RMS) cua waveform de tu phat hien
cac doan im lang that trong audio, thay vi doc alignment truc tiep tu model.
Day la bang chung KHACH QUAN BO SUNG, KHONG thay the viec nguoi dung tu
nghe that - ket qua cuoi cung van can 1 nguoi nghe thuc te de danh gia.

Chay: backend/.venv/Scripts/python.exe scratch_check/unverified/test_vieneu_pause_step5.py
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "vieneu_step5")
os.makedirs(OUT_DIR, exist_ok=True)

# CUNG 1 doan van voi Step 0 cu cua Piper (scratch_check/test_piper_pause_step0.py,
# xem git log 6409fee) - de so sanh truc tiep, cong bang giua 2 engine.
TEST_TEXT = (
    "- Anh đi đâu đấy?\n"
    "Cô ấy hỏi, giọng đầy lo lắng. Trời đã tối. "
    "Anh có chắc không? Đừng làm vậy! "
    "Cô ấy níu tay anh lại..."
)

# Ban KHONG dau cau (giu nguyen tu, bo het dau cau/xuong dong) - de so sanh
# tong do dai: neu dau cau THAT SU tao ngat nghi, ban co dau cau phai DAI
# HON ro ret so voi ban khong dau cau (cung so tu, cung noi dung).
TEST_TEXT_NO_PUNCT = (
    "Anh đi đâu đấy "
    "Cô ấy hỏi giọng đầy lo lắng Trời đã tối "
    "Anh có chắc không Đừng làm vậy "
    "Cô ấy níu tay anh lại"
)

VOICE_ID = "Đức Trí"


def _detect_silences(audio, sample_rate, min_silence_ms=30, silence_thresh_ratio=0.08):
    """Phat hien cac doan im lang THAT trong waveform bang RMS nang luong
    theo tung frame ngan (10ms) - phuong phap don gian, khong can forced
    alignment, dung duoc cho BAT KY engine nao (khong phu thuoc Piper's
    alignment API). Nguong tuong doi (ty le % so voi RMS trung binh toan
    doan) de tu thich nghi voi muc am luong khac nhau giua cac ban ghi."""
    import numpy as np

    frame_len = int(sample_rate * 0.01)  # 10ms/frame
    n_frames = len(audio) // frame_len
    frame_rms = np.array([
        np.sqrt(np.mean(audio[i * frame_len:(i + 1) * frame_len].astype(np.float64) ** 2))
        for i in range(n_frames)
    ])
    avg_rms = frame_rms.mean() or 1.0
    thresh = avg_rms * silence_thresh_ratio

    silences = []
    in_silence = False
    start_frame = 0
    for i, r in enumerate(frame_rms):
        if r < thresh and not in_silence:
            in_silence = True
            start_frame = i
        elif r >= thresh and in_silence:
            in_silence = False
            dur_ms = (i - start_frame) * 10
            if dur_ms >= min_silence_ms:
                silences.append((start_frame * 0.01, dur_ms))
    if in_silence:
        dur_ms = (n_frames - start_frame) * 10
        if dur_ms >= min_silence_ms:
            silences.append((start_frame * 0.01, dur_ms))
    return silences


def main():
    from vieneu import Vieneu

    print("Dang khoi tao Vieneu()...")
    vieneu = Vieneu()
    sample_rate = vieneu.sample_rate
    print(f"sample_rate = {sample_rate}\n")

    print(f"Van ban CO dau cau:\n{TEST_TEXT}\n")
    audio_with = vieneu.infer(TEST_TEXT, voice=VOICE_ID)
    path_with = os.path.join(OUT_DIR, "step5_with_punctuation.wav")
    vieneu.save(audio_with, path_with)
    dur_with = len(audio_with) / sample_rate
    print(f"Da luu: {path_with} ({dur_with:.2f}s)\n")

    print(f"Van ban KHONG dau cau (cung tu, khong dau):\n{TEST_TEXT_NO_PUNCT}\n")
    audio_without = vieneu.infer(TEST_TEXT_NO_PUNCT, voice=VOICE_ID)
    path_without = os.path.join(OUT_DIR, "step5_without_punctuation.wav")
    vieneu.save(audio_without, path_without)
    dur_without = len(audio_without) / sample_rate
    print(f"Da luu: {path_without} ({dur_without:.2f}s)\n")

    print(f"=== So sanh tong do dai ===")
    print(f"  Co dau cau:    {dur_with:.3f}s")
    print(f"  Khong dau cau: {dur_without:.3f}s")
    diff = dur_with - dur_without
    print(f"  Chenh lech:    {diff:+.3f}s ({diff / dur_without * 100:+.1f}%)")

    print(f"\n=== Phat hien khoang lang that trong ban CO dau cau (RMS-based) ===")
    silences_with = _detect_silences(audio_with, sample_rate)
    if not silences_with:
        print("  KHONG phat hien khoang lang nao >= 30ms trong toan bo doan audio.")
    else:
        for t, dur_ms in silences_with:
            print(f"  tai ~{t:.2f}s: khoang lang {dur_ms:.0f}ms")

    print(f"\n=== Phat hien khoang lang trong ban KHONG dau cau (doi chieu) ===")
    silences_without = _detect_silences(audio_without, sample_rate)
    if not silences_without:
        print("  KHONG phat hien khoang lang nao >= 30ms.")
    else:
        for t, dur_ms in silences_without:
            print(f"  tai ~{t:.2f}s: khoang lang {dur_ms:.0f}ms")

    print(f"\n=== KET LUAN SO BO (bang chung khach quan, KHONG thay the nghe that) ===")
    print(f"So khoang lang phat hien - co dau cau: {len(silences_with)}, "
          f"khong dau cau: {len(silences_without)}")
    if len(silences_with) > len(silences_without) and diff > 0.15:
        print("=> Co dau hieu VieNeu-TTS THUC SU tao them khoang lang o dau cau "
              "(nhieu khoang lang hon VA dai hon ro ret khi co dau cau). Can nghe "
              "that de xac nhan co TU NHIEN/PHAN BIET DUOC giua cac loai dau cau hay khong.")
    else:
        print("=> KHONG thay bang chung ro rang rang dau cau tao them khoang lang dang ke. "
              "Co the Section 7.3 (ngat nghi theo dau cau) VAN can thiet voi VieNeu-TTS, "
              "giong nhu da can voi Piper. Can nghe that de xac nhan.")


if __name__ == "__main__":
    main()
