"""Section 7.3 - test tich hop THAT: 1 chunk ~250-tu, nhieu thoai, qua Piper
that + concat_with_variable_silence() that (ffmpeg that). Do so manh, kiem
tra seam (click/pop) tai tung diem noi bang cach do buoc nhay bien do dot
ngot ngay tai vi tri ghep - day la dau hieu khach quan cua click/pop, khong
thay the viec nguoi nghe THAT tu nghe, nen cung gui file cho nguoi dung.

Chay: python scratch_check/test_section73_integration.py
"""
import os
import sys
import wave

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.punctuation_pauses import split_chunk_by_punctuation
from pipeline.audio_postprocess import get_ffmpeg, concat_with_variable_silence

VOICE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "piper_voices", "vi_VN-vais1000-medium.onnx")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "section73")
os.makedirs(OUT_DIR, exist_ok=True)

# Doan van ~250 tu, nhieu thoai (kiem tra do phan manh o kich ban "xau nhat"
# - nhieu dau cau, nhieu dong thoai) - mo phong 1 chunk that ma
# text_splitter.py se tao ra tu 1 chuong tieu thuyet co doi thoai day dac.
TEST_CHUNK = """Trời đã tối hẳn, sương giăng kín cả khu rừng. Lý Phong dừng bước, nhíu mày nhìn về phía xa, tay nắm chặt thanh kiếm bên hông.
- Có ai đó đang theo dõi chúng ta.
Tiểu Yến giật mình, quay đầu lại nhìn quanh, giọng run rẩy.
- Anh có chắc không? Em không thấy gì cả.
- Ta chắc chắn. Đã hai lần rồi, có tiếng bước chân theo sau...
Cả hai im lặng một lúc lâu, chỉ còn tiếng gió rít qua kẽ lá. Đột nhiên, một bóng đen lao vút qua, nhanh như chớp!
- Là ai? Ra mặt đi!
Không có tiếng trả lời. Lý Phong siết chặt kiếm, bước chậm rãi về phía trước, từng bước một, thận trọng.
- Đừng đi một mình, nguy hiểm lắm!
Tiểu Yến kéo tay anh lại, ánh mắt đầy lo lắng. Lý Phong quay lại nhìn nàng, khẽ mỉm cười trấn an.
- Yên tâm, ta sẽ không sao đâu.
Nói rồi, hắn tiếp tục tiến về phía khu rừng rậm rạp, nơi bóng tối dường như nuốt chửng mọi thứ."""


def _wav_duration_s(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


def _read_wav_samples(path):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        data = w.readframes(n)
        return np.frombuffer(data, dtype=np.int16), w.getframerate()


def _detect_seam_artifacts(path, silence_starts_s, silence_ends_s, sample_rate=24000):
    """Do buoc nhay bien do (|sample[i] - sample[i-1]|) ngay TRUOC/SAU moi
    khoang lang - buoc nhay bat thuong lon (so voi bien do trung binh cua
    tin hieu xung quanh) la dau hieu khach quan cua click/pop tai diem noi
    file. Day KHONG thay the viec nguoi nghe that su, chi la 1 phep do
    khach quan bo sung."""
    samples, sr = _read_wav_samples(path)
    issues = []
    for i, (s_start, s_end) in enumerate(zip(silence_starts_s, silence_ends_s)):
        start_idx = int(s_start * sr)
        end_idx = int(s_end * sr)
        window = 50  # so sample truoc/sau diem noi de tinh bien do tham chieu
        for label, idx in [("bat_dau_lang", start_idx), ("ket_thuc_lang", end_idx)]:
            if idx < window or idx + window >= len(samples):
                continue
            local_region = samples[idx - window:idx + window].astype(np.float64)
            local_rms = np.sqrt(np.mean(local_region ** 2)) or 1.0
            jump = abs(int(samples[idx]) - int(samples[idx - 1])) if idx > 0 else 0
            # Nguong tuy y: buoc nhay > 8000 (~25% full-scale int16) VA lon
            # hon nhieu lan RMS cuc bo duoc coi la nghi ngo click/pop.
            if jump > 8000 and jump > local_rms * 3:
                issues.append((i, label, jump, local_rms))
    return issues


def main():
    ffmpeg = get_ffmpeg()

    print(f"Tong so tu trong chunk: {len(TEST_CHUNK.split())}")
    pieces, pause_ms = split_chunk_by_punctuation(TEST_CHUNK)
    print(f"\nSo manh sau khi tach: {len(pieces)}")
    for i, p in enumerate(pieces):
        pause_after = f" (lang {pause_ms[i]}ms sau)" if i < len(pause_ms) else " (cuoi chunk)"
        print(f"  [{i}] ({len(p.split())} tu){pause_after}: {p!r}")

    print("\nDang tai Piper...")
    from piper.voice import PiperVoice
    voice = PiperVoice.load(VOICE_PATH)

    piece_wavs = []
    for i, piece in enumerate(pieces):
        path = os.path.join(OUT_DIR, f"piece_{i:02d}.wav")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(voice.config.sample_rate)
            voice.synthesize_wav(piece, wf)
        piece_wavs.append(path)
        print(f"  piece {i}: {_wav_duration_s(path):.2f}s")

    silence_s = [ms / 1000.0 for ms in pause_ms]
    out_path = os.path.join(OUT_DIR, "section73_full_chunk.wav")
    concat_with_variable_silence(ffmpeg, piece_wavs, silence_s, out_path, sample_rate=voice.config.sample_rate)

    total_dur = _wav_duration_s(out_path)
    print(f"\nDa ghep xong: {out_path} ({total_dur:.2f}s tong)")

    # Tinh vi tri (giay) cua tung khoang lang trong file da ghep, de do seam.
    cursor = 0.0
    silence_starts, silence_ends = [], []
    for i, piece_path in enumerate(piece_wavs):
        cursor += _wav_duration_s(piece_path)
        if i < len(silence_s):
            silence_starts.append(cursor)
            cursor += silence_s[i]
            silence_ends.append(cursor)

    issues = _detect_seam_artifacts(out_path, silence_starts, silence_ends, sample_rate=voice.config.sample_rate)
    print(f"\n=== Kiem tra seam (click/pop) tai {len(silence_s)} diem noi ===")
    if issues:
        print(f"[PHAT HIEN {len(issues)} diem nghi ngo]:")
        for idx, label, jump, rms in issues:
            print(f"  diem noi #{idx} ({label}): buoc nhay bien do={jump} (RMS cuc bo={rms:.0f})")
    else:
        print("Khong phat hien buoc nhay bien do bat thuong nao tai cac diem noi "
              "(kiem tra khach quan qua bien do - KHONG thay the viec nghe that).")


if __name__ == "__main__":
    main()
