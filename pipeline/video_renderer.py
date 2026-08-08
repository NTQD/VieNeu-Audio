"""
Video Renderer: Ghép Ảnh + Audio + Subtitles thành Video MP4.
Tự động dò encoder H.264 phần cứng khả dụng trên máy đang chạy
(NVIDIA NVENC -> Intel Quick Sync -> libx264 phần mềm, luôn chạy được)
thay vì ép cứng h264_qsv — h264_qsv sẽ crash ngay trên máy không có
card Intel (vd. Google Colab dùng GPU NVIDIA T4).
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

# Flags riêng cho từng encoder (mỗi loại nhận tham số chất lượng khác nhau).
_ENCODER_ARGS = {
    "h264_nvenc": ["-preset", "medium", "-cq", "23", "-b:v", "0", "-pix_fmt", "yuv420p"],
    "h264_qsv":   ["-preset", "medium", "-global_quality", "25", "-pix_fmt", "nv12"],
    "libx264":    ["-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p"],
}
# Thứ tự ưu tiên khi tự động dò: GPU NVIDIA (vd. Colab T4) -> Intel Quick Sync -> CPU (luôn có).
_ENCODER_PRIORITY = ["h264_nvenc", "h264_qsv", "libx264"]

def _encoder_works(ffmpeg, encoder):
    """Encode thử 1 frame nhỏ để biết encoder có PHẦN CỨNG tương ứng thật sự,
    chứ không chỉ được ffmpeg build hỗ trợ (compiled-in nhưng không có card)."""
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
        "-i", "color=black:s=64x64:d=0.1", "-frames:v", "1",
        "-c:v", encoder, "-f", "null", "-",
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=15)
        return True
    except Exception:
        return False

def pick_video_encoder(ffmpeg, preferred=None):
    """Chọn encoder H.264 tốt nhất khả dụng trên máy hiện tại.

    ``preferred`` ép dùng đúng 1 encoder (bỏ qua dò tự động); để None sẽ dò
    theo _ENCODER_PRIORITY và luôn có libx264 làm phương án cuối (chạy được
    trên mọi máy, kể cả không có GPU).
    """
    candidates = [preferred] if preferred else _ENCODER_PRIORITY
    for enc in candidates:
        if enc and _encoder_works(ffmpeg, enc):
            return enc
    return "libx264"

def render_video(audio_path, image_path, srt_path=None, output_path=None, font_size=20, encoder=None):
    ffmpeg = get_ffmpeg()
    if not output_path: output_path = os.path.splitext(audio_path)[0] + ".mp4"
    if not srt_path: srt_path = os.path.splitext(audio_path)[0] + ".srt"

    chosen = pick_video_encoder(ffmpeg, preferred=encoder)
    encoder_args = _ENCODER_ARGS.get(chosen, _ENCODER_ARGS["libx264"])

    clean_srt_path = srt_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        ffmpeg, "-y", "-loop", "1", "-i", image_path, "-i", audio_path,
        "-vf", f"subtitles='{clean_srt_path}':force_style='FontSize={font_size},Alignment=2,MarginV=30'",
        "-c:v", chosen, *encoder_args,
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
        output_path
    ]
    subprocess.run(cmd, check=True)
    return chosen

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio")
    parser.add_argument("image")
    parser.add_argument("--srt", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--font", type=int, default=20)
    parser.add_argument(
        "--encoder", default=None, choices=list(_ENCODER_ARGS.keys()),
        help="Ép dùng 1 encoder cụ thể thay vì tự dò (vd: libx264 để luôn chạy trên CPU)",
    )
    args = parser.parse_args()
    used = render_video(args.audio, args.image, args.srt, args.out, args.font, encoder=args.encoder)
    print(f"✅ Encoder dùng: {used}")

if __name__ == "__main__":
    main()
