import os
import sys
import re
import gc
import gradio as gr
from concurrent.futures import ThreadPoolExecutor

# Thêm đường dẫn để import các module local và SDK
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, "src")

for p in [current_dir, project_root, src_path]:
    if p not in sys.path:
        sys.path.append(p)

from text_splitter import split_text_for_tts
from text_normalizer import normalize_text_for_tts
from vieneu import Vieneu

# ===== GLOBAL STATE =====
tts = None
selected_voice = None
voice_list_cache = []

SAMPLE_TEXT = "rộng thêm 71,173.2 m, tức là hơn 71 km chỉ số GDP tăng 8.02%; tốc độ là 1/1000 giây. hắn tên Elyudelin. Boss cấp Trụ Thần từ level 400-499. chỉ số 10^20"
OUTPUT_DIR = os.path.join(project_root, "outputs")


def detect_chapter_range(text):
    matches = re.findall(r'[Cc]h(?:ương|apter)\s*(\d+)', text)
    if not matches: return None
    nums = sorted([int(m) for m in matches])
    if len(nums) == 1: return f"{nums[0]}"
    return f"{nums[0]}-{nums[-1]}"

def init_tts():
    global tts
    if tts is None:
        tts = Vieneu(emotion="storytelling")
    return tts

def load_preset_voices():
    global voice_list_cache
    engine = init_tts()
    voice_list_cache = engine.list_preset_voices()
    choices = [f"{desc} (ID: {vid})" for desc, vid in voice_list_cache]
    if not choices:
        return gr.update(choices=["Không tìm thấy giọng nào"], value=None), "❌ Không tải được danh sách giọng."
    return gr.update(choices=choices, value=choices[0]), f"✅ Đã tải {len(choices)} giọng."

def select_preset_voice(choice):
    global selected_voice
    if not choice: return "❌ Chưa chọn giọng.", gr.update()
    engine = init_tts()
    voice_id = choice.split("(ID: ")[1][:-1]
    selected_voice = engine.get_preset_voice(voice_id)
    gr.Info(f"✅ Đã chọn: {choice}")
    return f"✅ Đã chọn: {choice}", gr.Tabs(selected=1)

def generate_sample():
    if selected_voice is None: return None, "❌ Chưa chọn giọng đọc."
    engine = init_tts()
    normalized = normalize_text_for_tts(SAMPLE_TEXT)
    audio = engine.infer(text=normalized, voice=selected_voice)
    return (engine.sample_rate, audio), "✅ Đã tạo bản mẫu."

def process_chapter(input_file, progress=gr.Progress(track_tqdm=False)):
    if selected_voice is None: return "❌ Chưa chọn giọng. Quay lại Bước 1.", []
    file_path = input_file.name if input_file else "input.txt"
    if not os.path.exists(file_path): return f"❌ Không tìm thấy file: {file_path}", []

    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    if not text.strip(): return "❌ File trống.", []

    text = normalize_text_for_tts(text)
    engine = init_tts()

    chapter_num = detect_chapter_range(text)
    prefix = f"C_{chapter_num}" if chapter_num else "part"
    chapter_dir = os.path.join(OUTPUT_DIR, prefix)
    os.makedirs(chapter_dir, exist_ok=True)

    # Lưu text gốc vào thư mục chương để subtitle_generator dùng
    text_save_path = os.path.join(chapter_dir, f"{prefix}.txt")
    with open(text_save_path, "w", encoding="utf-8") as tf:
        tf.write(text)

    # Chia nhỏ văn bản theo chương
    chapter_texts = re.split(r'(?i)(?=[Cc]h(?:ương|apter)\s*\d+)', text)
    chapter_texts = [c.strip() for c in chapter_texts if c.strip()]
    if not chapter_texts:
        chapter_texts = [text]

    generated_files = []
    total_chunks = sum(len(split_text_for_tts(c, 250)) for c in chapter_texts)
    log = f"📖 Chương {chapter_num or '???'} — {total_chunks} phần\n"
    
    global_idx = 0
    for c_idx, chap_text in enumerate(chapter_texts):
        chunks = split_text_for_tts(chap_text, 250)
        for p_idx, chunk in enumerate(chunks):
            filename = f"{prefix}_c{c_idx+1:02d}_p{p_idx+1:02d}.wav"
            output_file = os.path.join(chapter_dir, filename)
            word_count = len(chunk.split())
            progress((global_idx, total_chunks), desc=f"Render {filename} ({word_count} từ)")
            audio = engine.infer(text=chunk, voice=selected_voice)
            engine.save(audio, output_file)
            generated_files.append(os.path.abspath(output_file))
            log += f"✅ {filename} ({word_count} từ)\n"
            global_idx += 1

    gc.collect()
    log += f"\n🎉 HOÀN TẤT! {total_chunks} file .wav"
    log += f"\n📂 {os.path.abspath(chapter_dir)}"
    return log, generated_files

def run_postprocess(input_file, bgm_file, bgm_volume, silence_dur, bg_image, font_size, progress=gr.Progress(track_tqdm=False)):
    """Chạy toàn bộ pipeline: Hậu kỳ Audio -> Subtitle -> Render Video."""
    from audio_postprocess import get_ffmpeg, get_wav_files, concat_with_silence, mix_bgm
    from subtitle_generator import generate_srt
    from video_renderer import render_video

    # Xác định thư mục chương từ bước 3
    file_path = input_file.name if input_file else "input.txt"
    if not os.path.exists(file_path):
        return "❌ Chưa có file text. Hãy render audio ở Bước 3 trước.", None

    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    text = normalize_text_for_tts(text)
    chapter_num = detect_chapter_range(text)
    prefix = f"C_{chapter_num}" if chapter_num else "part"
    chapter_dir = os.path.join(OUTPUT_DIR, prefix)

    if not os.path.isdir(chapter_dir):
        return f"❌ Thư mục chương không tồn tại: {chapter_dir}\nHãy chạy Bước 3 trước.", None

    log = ""
    try:
        ffmpeg = get_ffmpeg()
        log += f"🛠️ FFmpeg found: {ffmpeg}\n"
    except FileNotFoundError:
        return "❌ FFmpeg chưa cài. Chạy: winget install Gyan.FFmpeg rồi khởi động lại.", None

    wav_files = get_wav_files(chapter_dir)
    if not wav_files:
        return f"❌ Không tìm thấy file .wav trong {chapter_dir}. Hãy chạy Bước 3 trước.", None

    # === BƯỚC 4a: Ghép audio + silence ===
    progress(0.1, desc="Đang ghép audio...")
    log += "[1/3] GHÉP AUDIO\n"
    merged_wav = os.path.join(chapter_dir, f"{prefix}_merged.wav")
    concat_with_silence(ffmpeg, wav_files, silence_dur, merged_wav)
    log += f"✅ Ghép {len(wav_files)} file, silence={silence_dur}s\n"

    # === BƯỚC 4b: Trộn BGM (nếu có) ===
    final_audio = merged_wav
    if bgm_file is not None:
        bgm_path = bgm_file.name if hasattr(bgm_file, 'name') else bgm_file
        if os.path.isfile(bgm_path):
            progress(0.25, desc="Đang trộn nhạc nền...")
            log += f"\n🎵 TRỘN BGM (volume: {bgm_volume})\n"
            bgm_wav = os.path.join(chapter_dir, f"{prefix}_final.wav")
            mix_bgm(ffmpeg, merged_wav, bgm_path, bgm_wav, bgm_volume)
            final_audio = bgm_wav
            log += "✅ Đã trộn nhạc nền\n"

    # === BƯỚC 5: Tạo phụ đề từ text gốc ===
    progress(0.4, desc="Đang tạo phụ đề...")
    log += "\n[2/3] TẠO PHỤ ĐỀ (từ text gốc)\n"
    # Lưu text gốc nếu chưa có
    text_save_path = os.path.join(chapter_dir, f"{prefix}.txt")
    if not os.path.isfile(text_save_path):
        with open(text_save_path, "w", encoding="utf-8") as tf:
            tf.write(text)
    srt_path = generate_srt(chapter_dir, text_save_path, silence_dur, max_chars=60)
    if not srt_path:
        return log + "❌ Lỗi tạo phụ đề.", None
    log += f"✅ Đã tạo: {os.path.basename(srt_path)}\n"

    # === BƯỚC 6: Render video ===
    if bg_image is None:
        return log + "\n⚠️ Chưa chọn ảnh nền → Dừng ở bước audio + subtitle.\nUpload ảnh nền để render video.", None

    progress(0.5, desc="Đang render video (Intel QSV)...")
    log += "\n[3/3] RENDER VIDEO (Intel QSV)\n"
    img_path = bg_image.name if hasattr(bg_image, 'name') else bg_image
    out_mp4 = os.path.join(chapter_dir, f"{prefix}_video.mp4")
    render_video(final_audio, img_path, srt_path, out_mp4, font_size=font_size)

    if os.path.isfile(out_mp4):
        size_mb = os.path.getsize(out_mp4) / (1024 * 1024)
        log += f"✅ Video: {os.path.basename(out_mp4)} ({size_mb:.1f} MB)\n"
        log += f"\n🎉 PIPELINE HOÀN TẤT!"
        progress(1.0, desc="Hoàn tất!")
        return log, out_mp4
    else:
        log += "❌ Lỗi render video. Kiểm tra log FFmpeg."
        return log, None

# ===== GIAO DIỆN GRADIO =====
with gr.Blocks(title="VieNeu-TTS Auto Reader", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🦜 VieNeu-TTS — Sản xuất Audiobook tự động")
    gr.Markdown("**Quy trình khép kín:** Chọn giọng → Nghe mẫu → Render audio → Hậu kỳ & Render video")

    with gr.Tabs() as tabs:
        # ========== BƯỚC 1 ==========
        with gr.Tab("① Chọn giọng", id=0):
            gr.Markdown("### Chọn giọng đọc từ danh sách preset")
            btn_load = gr.Button("📂 Tải danh sách giọng", variant="secondary")
            preset_dropdown = gr.Dropdown(label="Chọn giọng preset", choices=[], interactive=True)
            btn_select_preset = gr.Button("✅ Xác nhận giọng", variant="primary")
            load_status = gr.Textbox(label="Trạng thái tải", interactive=False)
            voice_status = gr.Textbox(label="Trạng thái chọn giọng", interactive=False)

            btn_load.click(fn=load_preset_voices, outputs=[preset_dropdown, load_status])
            btn_select_preset.click(fn=select_preset_voice, inputs=preset_dropdown, outputs=[voice_status, tabs])

        # ========== BƯỚC 2 ==========
        with gr.Tab("② Nghe mẫu", id=1):
            gr.Markdown("### Tạo bản đọc thử để kiểm tra giọng đã chọn")
            btn_sample = gr.Button("🎤 Tạo bản mẫu", variant="primary")
            sample_audio = gr.Audio(label="Bản mẫu", elem_id="sample_player")
            speed_selector = gr.Dropdown(
                label="🔊 Tốc độ phát",
                choices=["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "1.75x", "2.0x"],
                value="1.0x",
                interactive=True
            )
            sample_status = gr.Textbox(label="Trạng thái", interactive=False)

            speed_selector.change(
                fn=lambda s: f"✅ Tốc độ: {s}",
                inputs=speed_selector,
                outputs=sample_status,
                js="""(speed) => {
                    window.currentSpeed = parseFloat(speed);
                    const apply = () => {
                        const audios = document.querySelectorAll('#sample_player audio');
                        audios.forEach(a => { a.playbackRate = window.currentSpeed; });
                    };
                    apply();
                    let count = 0;
                    const itv = setInterval(() => { apply(); if(++count > 12) clearInterval(itv); }, 250);
                    return speed;
                }"""
            )

            btn_sample.click(
                fn=generate_sample,
                outputs=[sample_audio, sample_status],
                js="""() => {
                    const itv = setInterval(() => {
                        const audios = document.querySelectorAll('#sample_player audio');
                        if (audios.length > 0) {
                            audios.forEach(a => { a.playbackRate = window.currentSpeed || 1.0; });
                            clearInterval(itv);
                        }
                    }, 500);
                    setTimeout(() => clearInterval(itv), 10000);
                }"""
            )

        # ========== BƯỚC 3 ==========
        with gr.Tab("③ Render Audio", id=2):
            gr.Markdown("### Upload file .txt chương truyện để tạo audio")
            gr.Markdown("*Để trống sẽ dùng file `input.txt` mặc định.*")
            input_file = gr.File(label="File chương truyện (.txt)", file_types=[".txt"])
            btn_render = gr.Button("🚀 Bắt đầu render audio", variant="primary")
            render_log = gr.Textbox(label="Nhật ký render", lines=12, interactive=False)
            gr.Markdown("---")
            gr.Markdown("### ⬇️ File audio đã tạo")
            download_files = gr.File(label="Tải xuống file .wav", file_count="multiple", interactive=False)

            btn_render.click(fn=process_chapter, inputs=input_file, outputs=[render_log, download_files])

        # ========== BƯỚC 4 ==========
        with gr.Tab("④ Hậu kỳ & Video", id=3):
            gr.Markdown("### Ghép audio → Tạo phụ đề → Render video tự động")
            gr.Markdown("*Sử dụng cùng file .txt đã upload ở Bước 3.*")

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("#### 📂 Nguồn dữ liệu")
                    pp_input_file = gr.File(label="File .txt chương truyện (giống Bước 3)", file_types=[".txt"])
                    pp_bg_image = gr.File(label="🖼️ Ảnh nền video (jpg/png)", file_types=[".jpg", ".jpeg", ".png"])

                with gr.Column(scale=1):
                    gr.Markdown("#### ⚙️ Tuỳ chỉnh")
                    pp_bgm = gr.File(label="🎵 Nhạc nền BGM (tuỳ chọn)", file_types=[".mp3", ".wav"])
                    pp_bgm_vol = gr.Slider(label="Âm lượng BGM", minimum=0.01, maximum=0.2, value=0.05, step=0.01)
                    pp_silence = gr.Slider(label="Khoảng lặng giữa các phần (giây)", minimum=0.1, maximum=3.0, value=0.5, step=0.1)
                    pp_font = gr.Slider(label="Cỡ chữ phụ đề", minimum=14, maximum=40, value=24, step=1)

            btn_pipeline = gr.Button("🎬 BẮT ĐẦU PIPELINE: Audio → Subtitle → Video", variant="primary", size="lg")
            pipeline_log = gr.Textbox(label="Nhật ký Pipeline", lines=15, interactive=False)
            gr.Markdown("---")
            gr.Markdown("### 🎥 Video hoàn chỉnh")
            output_video = gr.Video(label="Video đầu ra")

            btn_pipeline.click(
                fn=run_postprocess,
                inputs=[pp_input_file, pp_bgm, pp_bgm_vol, pp_silence, pp_bg_image, pp_font],
                outputs=[pipeline_log, output_video]
            )

if __name__ == "__main__":
    app.launch()

