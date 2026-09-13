"""Step 4 cua yeu cau doi engine (2026-09-11) - kiem tra pipeline/vieneu_tts.py
that su hoat dong: dung dung genre->voice tu config, dung dung version check,
chap nhan tag cam xuc dang ngoac vuong trong text.

QUAN TRONG: chay bang backend/.venv (isolated), KHONG bang venv chung.
Chay: backend/.venv/Scripts/python.exe scratch_check/test_vieneu_tts_wrapper.py
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voxdirector.config import load_voice_presets
from pipeline.vieneu_tts import synthesize_to_file, get_sample_rate

presets = load_voice_presets()
voice_id = presets["genre_to_voice"]["kiem_hiep"]
print(f"genre_to_voice['kiem_hiep'] = {voice_id!r}")

sample_rate = get_sample_rate(voice_id)
print(f"sample_rate = {sample_rate}")

out_path = "scratch_check/out/test_vieneu_wrapper_output.wav"
os.makedirs(os.path.dirname(out_path), exist_ok=True)

text = "Lý Phong dừng bước [cười] trước cổng Hắc Vân Môn."
synthesize_to_file(text, voice_id, out_path)
print(f"Da luu: {out_path}")

import wave
with wave.open(out_path, "rb") as w:
    dur = w.getnframes() / w.getframerate()
print(f"Do dai audio: {dur:.2f}s")
print("[OK] pipeline/vieneu_tts.py hoat dong dung voi genre->voice config that.")
