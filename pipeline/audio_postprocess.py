"""
Audio Post-processing: Ghép các file .wav thành 1 file chương hoàn chỉnh.
"""

import os
import sys
import subprocess
import tempfile
import argparse
import re

# Thêm đường dẫn để import các module local
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def get_ffmpeg():
    """Tìm đường dẫn FFmpeg với cơ chế tìm kiếm sâu trên Windows."""
    for cmd in ["ffmpeg", "ffmpeg.exe"]:
        try:
            subprocess.run([cmd, "-version"], capture_output=True, check=True)
            return cmd
        except: continue

    local_appdata = os.environ.get("LOCALAPPDATA", "")
    user_profile = os.environ.get("USERPROFILE", "")
    potential_paths = [
        os.path.join(local_appdata, "Microsoft", "WinGet", "Links", "ffmpeg.exe"),
        "C:\\ffmpeg\\bin\\ffmpeg.exe",
        os.path.join(user_profile, "ffmpeg", "bin", "ffmpeg.exe"),
    ]
    winget_pkgs = os.path.join(local_appdata, "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_pkgs):
        for root, dirs, files in os.walk(winget_pkgs):
            if "ffmpeg.exe" in files and "bin" in root.lower():
                potential_paths.append(os.path.join(root, "ffmpeg.exe"))

    for path in potential_paths:
        if os.path.isfile(path): return path
    raise FileNotFoundError("FFmpeg không tìm thấy.")

def get_wav_files(chapter_dir):
    """Lấy danh sách file .wav part (không lấy file merged/final) — nếu không
    loại trừ, chạy lại hậu kỳ trên 1 chương đã có sẵn _merged.wav/_final.wav
    từ lần trước sẽ ghép luôn file đó vào, gây trùng lặp nội dung."""
    files = [f for f in os.listdir(chapter_dir)
             if f.lower().endswith(".wav") and "_merged" not in f and "_final" not in f]
    files.sort(key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    return [os.path.join(chapter_dir, f) for f in files]

def generate_silence(ffmpeg, duration_s, sample_rate=24000, output_path=None):
    if output_path is None: output_path = tempfile.mktemp(suffix=".wav")
    cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono", "-t", str(duration_s), "-c:a", "pcm_s16le", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path

def concat_with_variable_silence(ffmpeg, wav_files, silence_durations, output_path, sample_rate=24000):
    """Ghép N file .wav với N-1 khoảng lặng CÓ ĐỘ DÀI RIÊNG giữa mỗi cặp
    file liên tiếp — nguyên thuỷ dùng chung cho CẢ HAI cấp độ ngắt nghỉ của
    v5 (xem VoxDirectorAI_Technical_Spec.md Section 7.2/7.3), thay vì viết 2
    hàm ghép riêng biệt:
    - Section 7.2 (PAUSE_LONG, cấp THÔ — giữa các chunk ~250-từ do Alpha/Beta
      đánh dấu ngữ nghĩa): mỗi phần tử wav_files là audio đã render xong của
      1 CHUNK hoàn chỉnh.
    - Section 7.3 (dấu câu, cấp MỊN — bên trong 1 chunk, xem
      pipeline/punctuation_pauses.py): mỗi phần tử wav_files là audio của 1
      MẢNH nhỏ hơn (một phần của câu), sẽ được ghép lại thành audio hoàn
      chỉnh của chunk đó trước khi chunk đó lại được ghép ở cấp Section 7.2.

    silence_durations: list[float] (giây) — ĐÚNG len(wav_files) - 1 phần tử,
    khoảng lặng giữa wav_files[i] và wav_files[i+1]. Raise ValueError nếu
    sai số lượng, thay vì âm thầm cắt/lặp — 1 lỗi lệch-số-lượng ở đây nghĩa
    là code gọi hàm đã tính sai đâu đó, tốt hơn nên biết ngay.
    """
    if len(silence_durations) != len(wav_files) - 1:
        raise ValueError(
            f"Cần đúng {len(wav_files) - 1} khoảng lặng cho {len(wav_files)} file "
            f"({len(wav_files)} file → {len(wav_files) - 1} khoảng giữa), nhưng "
            f"nhận được {len(silence_durations)}."
        )

    silence_files = [generate_silence(ffmpeg, d, sample_rate=sample_rate) for d in silence_durations]

    concat_list = tempfile.mktemp(suffix=".txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for i, wav in enumerate(wav_files):
            f.write(f"file '{os.path.abspath(wav)}'\n")
            if i < len(wav_files) - 1:
                f.write(f"file '{os.path.abspath(silence_files[i])}'\n")

    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c:a", "pcm_s16le", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    for sf in silence_files:
        os.remove(sf)
    os.remove(concat_list)
    return output_path


def durations_from_boundary_flags(boundary_flags, default_silence_s, pause_long_ms=None):
    """Chuyen list boundary_flags (tu text_splitter.split_text_with_boundaries)
    thanh list do dai khoang lang (giay) - Section 7.2 cua spec (v5).

    "default" -> default_silence_s (mac dinh nguoi dung dieu chinh o UI).
    "pause_long" -> config.PAUSE_LONG_DURATION_MS / 1000.

    pause_long_ms=None thi doc tu config (import lazy o day de audio_postprocess
    khong bat buoc co voxdirector/ khi test 1 minh)."""
    if pause_long_ms is None:
        from voxdirector.config import PAUSE_LONG_DURATION_MS
        pause_long_ms = PAUSE_LONG_DURATION_MS
    pause_long_s = pause_long_ms / 1000.0
    return [
        pause_long_s if flag == "pause_long" else default_silence_s
        for flag in boundary_flags
    ]


def concat_with_silence(ffmpeg, wav_files, silence_duration, output_path):
    """Ghép các file .wav phần của 1 chương, chèn khoảng lặng ĐỀU (cùng 1 độ
    dài) giữa mỗi cặp file — wrapper tiện lợi giữ hành vi cũ (trước v5, khi
    chưa cần độ dài khác nhau theo từng ranh giới) bằng cách gọi
    concat_with_variable_silence() với cùng 1 giá trị lặp lại.

    Trước đây hàm này còn tự phát hiện "chuyển chương" (dựa vào số trong tên
    file dạng "_c<N>_p<M>.wav") để chèn khoảng lặng dài hơn (2.0s) tại điểm
    đó — điều này không còn cần thiết: kể từ khi Agent Alpha đảm nhiệm việc
    tách chương, MỖI thư mục chương luôn chỉ chứa các phần của ĐÚNG 1 chương
    — 1 lệnh gọi concat_with_silence() không bao giờ còn bắc qua ranh giới 2
    chương nữa, nên không còn "điểm chuyển chương" nào để phát hiện trong
    danh sách wav_files truyền vào.
    """
    return concat_with_variable_silence(
        ffmpeg, wav_files, [silence_duration] * (len(wav_files) - 1), output_path,
    )

def mix_bgm(ffmpeg, voice_path, bgm_path, output_path, bgm_volume=0.05):
    cmd = [ffmpeg, "-y", "-i", voice_path, "-stream_loop", "-1", "-i", bgm_path, "-filter_complex", f"[1:a]volume={bgm_volume}[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=3", "-c:a", "pcm_s16le", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chapter_dir")
    parser.add_argument("--silence", type=float, default=0.5)
    parser.add_argument("--bgm", type=str, default=None)
    parser.add_argument("--bgm-volume", type=float, default=0.05)
    args = parser.parse_args()
    ffmpeg = get_ffmpeg()
    wav_files = get_wav_files(args.chapter_dir)
    merged_path = os.path.join(args.chapter_dir, f"{os.path.basename(args.chapter_dir)}_merged.wav")
    concat_with_silence(ffmpeg, wav_files, args.silence, merged_path)
    if args.bgm:
        mix_bgm(ffmpeg, merged_path, args.bgm, merged_path.replace("_merged", "_final"), args.bgm_volume)

if __name__ == "__main__":
    main()
