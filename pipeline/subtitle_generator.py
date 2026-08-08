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

from text_splitter import split_text_for_tts

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

def generate_srt(chapter_dir, text_file=None, silence=0.5, max_chars=60):
    """Tạo SRT từ text gốc + duration .wav."""
    wav_files = get_wav_files(chapter_dir)
    if not wav_files: return None

    txt_path = text_file if text_file and os.path.isfile(text_file) else find_text_file(chapter_dir)
    if not txt_path: return None

    with open(txt_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    chapter_texts = re.split(r'(?i)(?=[Cc]h(?:ương|apter)\s*\d+)', full_text)
    chapter_texts = [c.strip() for c in chapter_texts if c.strip()]
    if not chapter_texts:
        chapter_texts = [full_text.strip()]

    chunks = []
    chunk_chapter_map = []
    for c_idx, chap_text in enumerate(chapter_texts):
        chap_chunks = split_text_for_tts(chap_text, max_words=250)
        chunks.extend(chap_chunks)
        chunk_chapter_map.extend([c_idx] * len(chap_chunks))

    pairs = min(len(chunks), len(wav_files))
    srt_entries = []
    index = 1
    cursor = 0.0

    for i in range(pairs):
        dur = get_wav_duration(wav_files[i])
        part_start = cursor
        part_end = cursor + dur

        sub_lines = split_text_to_subtitle_lines(chunks[i], max_chars)

        if i < pairs - 1:
            curr_c = chunk_chapter_map[i]
            next_c = chunk_chapter_map[i+1]
            current_silence = 2.0 if curr_c != next_c else silence
        else:
            current_silence = silence

        if not sub_lines:
            cursor = part_end + current_silence
            continue

        line_dur = dur / len(sub_lines)
        for j, line in enumerate(sub_lines):
            line_start = part_start + j * line_dur
            line_end = part_start + (j + 1) * line_dur
            srt_entries.append(f"{index}\n{format_ts(line_start)} --> {format_ts(line_end)}\n{line}\n")
            index += 1

        cursor = part_end + current_silence

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
