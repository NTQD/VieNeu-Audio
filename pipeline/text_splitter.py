"""Chia van ban thanh cac chunk ~250 tu de dua vao TTS engine (VieNeu-TTS -
Piper da bi go bo hoan toan 2026-09-11). Section 7.2 cua spec (v5): thay doi
duoc phep - moi [[PAUSE_LONG]] la 1 ranh gioi ep buoc, va tra ve them 1 danh
sach cho biet moi ranh gioi la loai pause-flagged hay word-count binh thuong
(audio_postprocess.py can biet de ap khoang lang khac nhau)."""

import re

from voxdirector.config import PAUSE_LONG_TOKEN


def split_text_for_tts(text, max_words=250):
    """Backward-compatible: chi tra ve list[str] chunks (khong co metadata
    boundary). Dung cho code cu chua switch sang API moi - moi chunk da bi
    strip sentinel [[PAUSE_LONG]]."""
    chunks, _ = split_text_with_boundaries(text, max_words)
    return chunks


def split_text_with_boundaries(text, max_words=250):
    """Chia text thanh chunks; tra ve (chunks, boundary_flags) voi:
    - chunks: list[str], moi phan tu KHONG chua sentinel [[PAUSE_LONG]] (da
      strip truoc khi dua vao TTS engine - engine khong hieu marker nay).
    - boundary_flags: list[str], do dai = len(chunks) - 1. Moi phan tu la
      "pause_long" (ranh gioi do sentinel ep) hoac "default" (ranh gioi word-
      count binh thuong). audio_postprocess.py doc list nay de chon khoang
      lang tuong ung.

    Quy tac Section 7.2 cua spec:
    - Sentinel [[PAUSE_LONG]] LUON ket thuc chunk hien tai (ngay ca khi chua
      day 250 tu) va bat dau chunk moi.
    - Ranh gioi word-count van hoat dong nhu cu khi khong co sentinel."""
    if not text.strip():
        return [], []

    parts = re.split(re.escape(PAUSE_LONG_TOKEN), text)

    chunks = []
    boundary_flags = []

    for part_idx, part in enumerate(parts):
        segments_in_part = _split_by_word_count(part, max_words)
        for seg_idx, seg in enumerate(segments_in_part):
            if not seg.strip():
                continue
            if chunks:
                # Ranh gioi giua chunk moi sap them va chunk truoc do:
                # - Neu day la segment DAU TIEN cua 1 part (khong phai part 0)
                #   thi ranh gioi la do sentinel [[PAUSE_LONG]] ep.
                # - Nguoc lai (segments trong cung 1 part) la word-count binh
                #   thuong.
                is_sentinel_boundary = (seg_idx == 0 and part_idx > 0)
                boundary_flags.append("pause_long" if is_sentinel_boundary else "default")
            chunks.append(seg.strip())

    return chunks, boundary_flags


def _split_by_word_count(text, max_words):
    """Chia 1 doan text theo cau (regex nhu ban goc v3) roi gom cac cau lai
    thanh chunk khong vuot qua max_words. Tach rieng ra thanh helper de
    split_text_with_boundaries() goi cho tung "part" giua cac sentinel."""
    if not text.strip():
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current_chunk = []
    current_word_count = 0
    for sentence in sentences:
        wc = len(sentence.split())
        if current_word_count + wc > max_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_word_count = 0
        current_chunk.append(sentence)
        current_word_count += wc
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks


if __name__ == "__main__":
    text = "Nội dung truyện dịch của bạn ở đây..."
    result = split_text_for_tts(text, 250)
    for i, chunk in enumerate(result):
        print(f"Part {i+1} ({len(chunk.split())} từ): {chunk}\n")
