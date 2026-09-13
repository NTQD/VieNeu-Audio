"""
Subtitle Generator: Tạo file .srt từ text gốc + duration các file .wav.
"""

import os
import sys
import re
import wave
import argparse

# Thêm đường dẫn để import các module local
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from text_splitter import split_text_for_tts, split_text_with_boundaries

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def get_wav_duration(wav_path):
    """Lấy duration (giây) của file .wav."""
    with wave.open(wav_path, 'r') as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / rate

def get_wav_files(chapter_dir):
    """Lấy danh sách file .wav part (không lấy file merged/final)."""
    files = [f for f in os.listdir(chapter_dir)
             if f.lower().endswith(".wav") and "_merged" not in f and "_final" not in f]
    files.sort(key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    return [os.path.join(chapter_dir, f) for f in files]

def find_text_file(chapter_dir):
    """Tìm file text gốc tương ứng với chương."""
    chapter_name = os.path.basename(chapter_dir)
    parent = os.path.dirname(chapter_dir)
    grandparent = os.path.dirname(parent)
    
    candidates = [
        os.path.join(chapter_dir, f"{chapter_name}.txt"),
        os.path.join(parent, f"{chapter_name}.txt"),
        os.path.join(grandparent, "input.txt"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

def split_text_to_subtitle_lines(text, max_chars=60):
    """Chia text thành các dòng phụ đề ngắn."""
    sentences = re.split(r'(?<=[.!?,;:])\s+', text.strip())
    lines = []
    current_line = ""
    
    for sentence in sentences:
        if len(current_line) + len(sentence) + 1 <= max_chars:
            current_line = (current_line + " " + sentence).strip()
        else:
            if current_line: lines.append(current_line)
            if len(sentence) > max_chars:
                words = sentence.split()
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) + 1 <= max_chars:
                        current_line = (current_line + " " + word).strip()
                    else:
                        if current_line: lines.append(current_line)
                        current_line = word
            else:
                current_line = sentence
    if current_line: lines.append(current_line)
    return lines

def format_ts(seconds):
    """Chuyển giây → HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def generate_srt(chapter_dir, text_file=None, silence=0.5, boundary_silences=None, max_chars=60):
    """Tạo SRT từ text gốc + duration .wav.

    text_file luôn là text của ĐÚNG 1 chương — Agent Alpha (xem
    voxdirector/agents/alpha_ingestion.py) đã phân tách chương ở tầng backend
    trước khi lưu file này, nên KHÔNG cần tự tách lại "Chương N" bằng regex ở
    đây nữa (trước đây có 1 bản regex-split trùng lặp y hệt logic tách
    chương, dễ lệch nếu 1 trong 2 chỗ đổi logic mà chỗ kia không đổi theo)."""
    wav_files = get_wav_files(chapter_dir)
    if not wav_files: return None

    txt_path = text_file if text_file and os.path.isfile(text_file) else find_text_file(chapter_dir)
    if not txt_path: return None

    with open(txt_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # boundary_silences (list[float], len = len(wav_files)-1): khoang lang
    # THAT giua tung cap file .wav lien tiep - Section 7.2 cua spec (v5) da
    # lam khoang lang KHONG con deu nhau nua (pause_long dai hon default).
    # Neu khong truyen vao, fallback ve "silence" (scalar, hanh vi cu truoc
    # v5) - nhung KHONG con dung cho chuong nao co pause_points that, vi se
    # lech thoi gian phu de sau moi diem pause_long (da xac nhan bang code:
    # PAUSE_LONG_DURATION_MS=1400ms != scalar default thuong ~300-500ms).
    if boundary_silences is None:
        chunks = split_text_for_tts(full_text.strip(), max_words=250)
        boundary_silences = [silence] * max(0, len(chunks) - 1)
    else:
        chunks, _ = split_text_with_boundaries(full_text.strip(), max_words=250)

    pairs = min(len(chunks), len(wav_files))
    srt_entries = []
    index = 1
    cursor = 0.0

    for i in range(pairs):
        dur = get_wav_duration(wav_files[i])
        part_start = cursor
        part_end = cursor + dur

        sub_lines = split_text_to_subtitle_lines(chunks[i], max_chars)

        gap = boundary_silences[i] if i < len(boundary_silences) else silence

        if not sub_lines:
            cursor = part_end + gap
            continue

        # Chia thời lượng của cả phần (dur) cho từng dòng phụ đề THEO TỈ LỆ
        # SỐ KÝ TỰ, không chia đều — 1 dòng dài đọc lâu hơn 1 dòng ngắn, chia
        # đều khiến dòng dài bị "chạy" trước lúc đọc xong và dòng ngắn bị giữ
        # lại quá lâu, gây cảm giác phụ đề nhanh/chậm hơn giọng đọc thật.
        # Đây vẫn là ước lượng theo độ dài chữ, không phải canh theo audio
        # thật (forced alignment) nên không tuyệt đối chính xác.
        total_chars = sum(len(l) for l in sub_lines) or 1
        line_start = part_start
        for j, line in enumerate(sub_lines):
            seg_dur = dur * (len(line) / total_chars)
            line_end = line_start + seg_dur
            srt_entries.append(f"{index}\n{format_ts(line_start)} --> {format_ts(line_end)}\n{line}\n")
            index += 1
            line_start = line_end

        cursor = part_end + gap

    chapter_name = os.path.basename(chapter_dir)
    srt_path = os.path.join(chapter_dir, f"{chapter_name}_merged.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_entries))
    return srt_path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chapter_dir")
    parser.add_argument("--text", default=None)
    parser.add_argument("--silence", type=float, default=0.5)
    parser.add_argument("--max-chars", type=int, default=60)
    args = parser.parse_args()
    generate_srt(args.chapter_dir, args.text, args.silence, args.max_chars)

if __name__ == "__main__":
    main()
