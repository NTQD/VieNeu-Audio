"""Tao san 1 lan (2026-09-12, yeu cau nguoi dung: "Voice Audition feature,
theo cach 1: tao san ca 23 giong 1 luot") - moi giong trong
data/voice_presets.json doc dung 1 cau mau CO NHAC TEN CHINH GIONG DO, luu
thanh file .wav tinh (khong sinh lai luc chay), phuc vu GET
/api/voice-preview/{voice_id} (xem backend/app/main.py).

VieNeu-TTS KHONG co san preview audio nhu cac giong dam may cua ElevenLabs
(khong co gi de "tai ve" - phai tu tong hop). Chi can chay LAI script nay neu
danh sach giong trong data/voice_presets.json thay doi.

QUAN TRONG - phai chay trong venv/moi truong co dung `vieneu` PyPI that
(backend/.venv hoac container backend) - xem voxdirector/config.py:
EXPECTED_VIENEU_VERSION.

Chay: python scripts/generate_voice_previews.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voxdirector.config import load_voice_presets
from pipeline.vieneu_tts import synthesize_to_file
from pipeline.voice_naming import slugify_voice_id

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "voice_previews"
)

SAMPLE_TEXT_TEMPLATE = (
    "Xin chào quý khách, tôi là {name}, chào mừng quý khách trải nghiệm hệ thống "
    "giọng đọc Vox Director, chúc quý khách có những trải nghiệm vui vẻ."
)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    presets = load_voice_presets()
    voices = presets["voices"]

    for i, voice in enumerate(voices):
        voice_id = voice["id"]
        slug = slugify_voice_id(voice_id)
        out_path = os.path.join(OUT_DIR, f"{slug}.wav")
        text = SAMPLE_TEXT_TEMPLATE.format(name=voice_id)
        print(f"[{i + 1}/{len(voices)}] {voice_id!r} -> {out_path}")
        synthesize_to_file(text, voice_id, out_path)

    print(f"\nHoàn tất: {len(voices)} preview đã lưu vào {OUT_DIR}")


if __name__ == "__main__":
    main()
