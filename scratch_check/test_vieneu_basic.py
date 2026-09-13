"""Step 2 cua yeu cau doi engine (2026-09-11) - kiem tra co ban VieNeu-TTS
qua duong dan CPU/ONNX toi thieu (torch-free), theo dung README chinh thuc.

Chay: python scratch_check/test_vieneu_basic.py
"""
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from vieneu import Vieneu

print("Dang khoi tao Vieneu() (mac dinh: v3 Turbo, CPU/ONNX vi khong co GPU)...")
t0 = time.perf_counter()
vieneu = Vieneu()
print(f"Khoi tao xong: {time.perf_counter() - t0:.2f}s\n")

print("Danh sach preset voices:")
voices = vieneu.list_preset_voices()
print(f"So luong: {len(voices)}")
for label, voice_id in voices:
    print(f"  - {label} ({voice_id})")

print("\nDang tong hop cau kiem tra...")
t0 = time.perf_counter()
audio = vieneu.infer("Xin chào, đây là VieNeu-TTS.", voice="Trúc Ly")
elapsed = time.perf_counter() - t0

out_path = "scratch_check/out/test_vieneu_output.wav"
import os
os.makedirs(os.path.dirname(out_path), exist_ok=True)
vieneu.save(audio, out_path)

sample_rate = 48000
audio_duration = len(audio) / sample_rate
rtf = elapsed / audio_duration if audio_duration > 0 else float("nan")

print(f"Da luu: {out_path}")
print(f"Thoi gian tong hop: {elapsed:.3f}s")
print(f"Do dai audio: {audio_duration:.3f}s")
print(f"RTF: {rtf:.4f} ({'nhanh hon' if rtf < 1 else 'cham hon'} real-time {1/rtf:.2f}x)" if rtf > 0 else "")
