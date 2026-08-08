"""
Make Video: Kịch bản tự động hóa 100% từ thư mục file .wav lẻ thành Video YouTube.
Quy trình: Ghép Audio (có BGM) -> Tạo Subtitle -> Render Video QSV.

Dùng: uv run python make_video.py outputs/C_1846 background.png
       uv run python make_video.py outputs/C_1846 background.png --bgm bgm/ambient.mp3
"""

import os
import sys
import argparse

# Thêm đường dẫn để import các module local
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)

from audio_postprocess import get_ffmpeg, get_wav_files, concat_with_silence, mix_bgm
from subtitle_generator import generate_srt
from video_renderer import render_video


sys.stdout.reconfigure(encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Tự động hoá: Audio Part -> Video Hoàn Chỉnh")
    parser.add_argument("chapter_dir", help="Thư mục chương (vd: outputs/C_1846)")
    parser.add_argument("image", help="Đường dẫn file ảnh nền (jpg/png)")
    parser.add_argument("--bgm", type=str, default=None, help="Đường dẫn file nhạc nền")
    parser.add_argument("--bgm-volume", type=float, default=0.05, help="Âm lượng BGM (0.0-1.0, mặc định: 0.05)")
    parser.add_argument("--silence", type=float, default=0.5, help="Khoảng lặng giữa các part (giây)")
    parser.add_argument("--text", default=None, help="Đường dẫn file text gốc (nếu không tự tìm được)")
    parser.add_argument("--font", type=int, default=24, help="Cỡ chữ phụ đề (mặc định: 24)")
    
    args = parser.parse_args()

    if not os.path.isdir(args.chapter_dir):
        print(f"❌ Thư mục không tồn tại: {args.chapter_dir}")
        sys.exit(1)
    if not os.path.isfile(args.image):
        print(f"❌ File ảnh không tồn tại: {args.image}")
        sys.exit(1)

    print("=" * 50)
    print("🚀 BẮT ĐẦU QUY TRÌNH AUTO RENDER VIDEO")
    print("=" * 50)

    ffmpeg = get_ffmpeg()
    chapter_name = os.path.basename(args.chapter_dir)
    wav_files = get_wav_files(args.chapter_dir)
    
    if not wav_files:
        print(f"❌ Không tìm thấy file .wav part trong: {args.chapter_dir}")
        sys.exit(1)

    # BƯỚC 1: AUDIO POST-PROCESSING
    print("\n[1/3] ĐANG XỬ LÝ AUDIO...")
    merged_wav = os.path.join(args.chapter_dir, f"{chapter_name}_merged.wav")
    concat_with_silence(ffmpeg, wav_files, args.silence, merged_wav)
    
    final_audio = merged_wav
    if args.bgm and os.path.isfile(args.bgm):
        print(f"🎵 Đang trộn nhạc nền...")
        bgm_wav = os.path.join(args.chapter_dir, f"{chapter_name}_final.wav")
        mix_bgm(ffmpeg, merged_wav, args.bgm, bgm_wav, args.bgm_volume)
        final_audio = bgm_wav

    # BƯỚC 2: SUBTITLE GENERATION
    print("\n[2/3] ĐANG TẠO PHỤ ĐỀ (TỪ TEXT GỐC)...")
    srt_path = generate_srt(args.chapter_dir, args.text, args.silence, max_chars=60)
    if not srt_path:
        print("❌ Lỗi tạo phụ đề. Dừng quy trình.")
        sys.exit(1)

    # BƯỚC 3: VIDEO RENDERING
    print("\n[3/3] ĐANG RENDER VIDEO (INTEL QSV)...")
    out_mp4 = os.path.join(args.chapter_dir, f"{chapter_name}_video.mp4")
    render_video(final_audio, args.image, srt_path, out_mp4, font_size=args.font)

    print("=" * 50)
    print("🎉 QUY TRÌNH HOÀN TẤT THÀNH CÔNG!")
    print(f"🎥 Video cuối: {os.path.abspath(out_mp4)}")
    print("=" * 50)

if __name__ == "__main__":
    main()
