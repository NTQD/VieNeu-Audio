"""Chuyen 1 voice_id (ten giong that cua VieNeu-TTS, vd. "Minh Đức", co dau
tieng Viet + khoang trang) thanh 1 slug an toan lam TEN FILE/URL path (vd.
"minh-duc") - dung CHUNG boi scripts/generate_voice_previews.py (luc tao file
.wav preview) VA backend/app/main.py (luc tra ve dung file cho GET
/api/voice-preview/{voice_id}) de dam bao 2 ben LUON khop nhau."""

import re
import unicodedata


def slugify_voice_id(voice_id: str) -> str:
    # "đ"/"Đ" khong tu tach dau qua NFD normalize (la 1 chu cai rieng trong
    # tieng Viet, khong phai "d" + dau) - phai doi tay truoc.
    s = voice_id.replace("Đ", "D").replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s
