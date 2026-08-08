"""
Video Renderer: Ghép Ảnh + Audio + Subtitles thành Video MP4 với Intel QSV.
"""

import os
import sys
import subprocess
import argparse

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

def render_video(audio_path, image_path, srt_path=None, output_path=None, font_size=20):
    ffmpeg = get_ffmpeg()
    if not output_path: output_path = os.path.splitext(audio_path)[0] + ".mp4"
    if not srt_path: srt_path = os.path.splitext(audio_path)[0] + ".srt"

    clean_srt_path = srt_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        ffmpeg, "-y", "-loop", "1", "-i", image_path, "-i", audio_path,
        "-vf", f"subtitles='{clean_srt_path}':force_style='FontSize={font_size},Alignment=2,MarginV=30'",
        "-c:v", "h264_qsv", "-preset", "medium", "-global_quality", "25",
        "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "nv12", "-shortest", "-movflags", "+faststart",
        output_path
    ]
    subprocess.run(cmd, check=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio")
    parser.add_argument("image")
    parser.add_argument("--srt", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--font", type=int, default=20)
    args = parser.parse_args()
    render_video(args.audio, args.image, args.srt, args.out, args.font)

if __name__ == "__main__":
    main()
