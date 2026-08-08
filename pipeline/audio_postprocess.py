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
    files = [f for f in os.listdir(chapter_dir) if f.lower().endswith(".wav")]
    files.sort(key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    return [os.path.join(chapter_dir, f) for f in files]

def generate_silence(ffmpeg, duration_s, sample_rate=24000, output_path=None):
    if output_path is None: output_path = tempfile.mktemp(suffix=".wav")
    cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono", "-t", str(duration_s), "-c:a", "pcm_s16le", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path

def concat_with_silence(ffmpeg, wav_files, silence_duration, output_path):
    silence_file = generate_silence(ffmpeg, silence_duration)
    chapter_silence_file = generate_silence(ffmpeg, 2.0)

    def get_chapter_idx(filename):
        m = re.search(r'_c(\d+)_p\d+\.wav', os.path.basename(filename))
        return int(m.group(1)) if m else 0

    concat_list = tempfile.mktemp(suffix=".txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for i, wav in enumerate(wav_files):
            f.write(f"file '{os.path.abspath(wav)}'\n")
            if i < len(wav_files) - 1:
                curr_c = get_chapter_idx(wav)
                next_c = get_chapter_idx(wav_files[i+1])
                if curr_c != next_c:
                    f.write(f"file '{os.path.abspath(chapter_silence_file)}'\n")
                else:
                    f.write(f"file '{os.path.abspath(silence_file)}'\n")

    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c:a", "pcm_s16le", output_path]
    subprocess.run(cmd, capture_output=True, check=True)
    os.remove(silence_file)
    os.remove(chapter_silence_file)
    os.remove(concat_list)
    return output_path

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
