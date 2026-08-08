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
# Số phần (part) đưa vào engine.infer_batch() mỗi lần gọi. Trên GPU, các phần
# trong 1 lô được gộp vào cùng forward pass thay vì chạy tuần tự từng phần
# (nhanh hơn nhiều trên Colab T4). Lô nhỏ hơn = lưu file thường xuyên hơn, ít
# mất việc hơn nếu mất kết nối giữa chừng; lô lớn hơn = ít round-trip GPU hơn.
BATCH_GROUP_SIZE = 8


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


def _chapter_dir_for(text_norm, source_path=None):
    """Suy ra (prefix, chapter_dir, chapter_num) từ text đã normalize, dùng chung cho mọi bước.

    Khi KHÔNG tìm thấy "Chương N" / "Chapter N" trong text (chapter_num = None),
    KHÔNG dùng chung 1 thư mục "part" tĩnh cho mọi file — làm vậy thì 2 chương
    khác nhau không có tiêu đề sẽ bị ghi đè/trộn lẫn vào cùng thư mục, và với
    cơ chế resume (bỏ qua file .wav đã có) thì chương thứ 2 còn có thể bị coi
    nhầm là "đã render xong" bằng nội dung của chương thứ 1. Thay vào đó, dùng
    tên file nguồn làm phần phân biệt.
    """
    chapter_num = detect_chapter_range(text_norm)
    if chapter_num:
        prefix = f"C_{chapter_num}"
    else:
        base = os.path.splitext(os.path.basename(source_path))[0] if source_path else "unknown"
        base = re.sub(r'[^\w\-]+', '_', base).strip('_') or "unknown"
        prefix = f"part_{base}"
    return prefix, os.path.join(OUTPUT_DIR, prefix), chapter_num

def _is_chapter_complete(chapter_dir, prefix, want_video):
    """Chương coi là XONG nếu: có ảnh nền -> đã có video; không có ảnh nền ->
    đã có audio ghép + phụ đề. Dùng để BỎ QUA hẳn 1 chương khi chạy batch,
    tránh làm lại từ đầu những chương đã xử lý xong ở lần chạy trước."""
    if want_video:
        p = os.path.join(chapter_dir, f"{prefix}_video.mp4")
    else:
        p = os.path.join(chapter_dir, f"{prefix}_merged.srt")
    return os.path.isfile(p) and os.path.getsize(p) > 0

def _render_chapter_audio(text_file_path, progress_cb=None):
    """Bước 3: normalize -> chia phần -> render audio (batch GPU, có resume).

    progress_cb(done, total, desc), nếu có, được gọi sau mỗi lô render.
    Trả về (chapter_dir, prefix, log, generated_files, total_chunks).
    """
    if selected_voice is None:
        raise RuntimeError("Chưa chọn giọng. Quay lại Bước 1.")
    if not os.path.exists(text_file_path):
        raise RuntimeError(f"Không tìm thấy file: {text_file_path}")

    with open(text_file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    if not text.strip():
        raise RuntimeError("File trống.")

    text = normalize_text_for_tts(text)
    engine = init_tts()

    prefix, chapter_dir, chapter_num = _chapter_dir_for(text, source_path=text_file_path)
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

    # Liệt kê TOÀN BỘ các phần cần có trước, kèm đường dẫn file đích.
    all_parts = []
    for c_idx, chap_text in enumerate(chapter_texts):
        chunks = split_text_for_tts(chap_text, 250)
        for p_idx, chunk in enumerate(chunks):
            filename = f"{prefix}_c{c_idx+1:02d}_p{p_idx+1:02d}.wav"
            output_file = os.path.abspath(os.path.join(chapter_dir, filename))
            all_parts.append({"filename": filename, "path": output_file, "text": chunk, "words": len(chunk.split())})

    total_chunks = len(all_parts)

    # Bỏ qua phần đã render sẵn (file .wav tồn tại và không rỗng) — quan trọng
    # khi chạy trên Colab vì phiên có thể ngắt kết nối giữa chừng; không có
    # bước này thì phải render lại từ đầu toàn bộ chương.
    already_done = [p for p in all_parts if os.path.isfile(p["path"]) and os.path.getsize(p["path"]) > 0]
    pending = [p for p in all_parts if p not in already_done]

    log = f"📖 Chương {prefix} — {total_chunks} phần"
    log += f" ({len(already_done)} đã render sẵn, bỏ qua)\n" if already_done else "\n"
    if chapter_num is None:
        log += (
            f"⚠️ Không tìm thấy \"Chương N\" / \"Chapter N\" trong văn bản — "
            f"dùng tên file làm thư mục ({prefix}) để tránh trộn lẫn với chương khác. "
            f"Nên thêm tiêu đề chương vào đầu file nếu có thể.\n"
        )

    done_count = len(already_done)
    # Render theo LÔ qua engine.infer_batch(): trên GPU các phần trong 1 lô
    # được gộp chung 1 forward pass (nhanh hơn nhiều so với gọi infer() tuần
    # tự từng phần); trên CPU vẫn chạy đúng, chỉ là tuần tự bên trong SDK.
    for i in range(0, len(pending), BATCH_GROUP_SIZE):
        group = pending[i:i + BATCH_GROUP_SIZE]
        if progress_cb:
            progress_cb(done_count, total_chunks, f"render lô {i // BATCH_GROUP_SIZE + 1} ({len(group)} phần)")
        wavs = engine.infer_batch(texts=[g["text"] for g in group], voice=selected_voice)
        for part, audio in zip(group, wavs):
            engine.save(audio, part["path"])
            log += f"✅ {part['filename']} ({part['words']} từ)\n"
            done_count += 1

    gc.collect()
    generated_files = [p["path"] for p in all_parts]
    log += f"🎉 Audio xong: {total_chunks} file .wav\n"
    return chapter_dir, prefix, log, generated_files, total_chunks

def _run_postprocess_core(text_file_path, bgm_path, bgm_volume, silence_dur, bg_image_path, font_size, progress_cb=None):
    """Bước 4: ghép audio -> trộn BGM (nếu có) -> tạo phụ đề -> render video (nếu có ảnh nền).

    progress_cb(fraction 0..1, desc), nếu có, được gọi ở mỗi giai đoạn.
    Trả về (chapter_dir, prefix, log, video_path_or_None).
    """
    from audio_postprocess import get_ffmpeg, get_wav_files, concat_with_silence, mix_bgm
    from subtitle_generator import generate_srt
    from video_renderer import render_video

    with open(text_file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    text = normalize_text_for_tts(text)
    prefix, chapter_dir, _chapter_num = _chapter_dir_for(text, source_path=text_file_path)

    if not os.path.isdir(chapter_dir):
        raise RuntimeError(f"Thư mục chương không tồn tại: {chapter_dir}. Chưa render audio.")

    log = ""
    ffmpeg = get_ffmpeg()  # ném FileNotFoundError nếu chưa cài — để caller xử lý
    log += f"🛠️ FFmpeg: {ffmpeg}\n"

    wav_files = get_wav_files(chapter_dir)
    if not wav_files:
        raise RuntimeError(f"Không tìm thấy file .wav trong {chapter_dir}.")

    if progress_cb: progress_cb(0.1, "đang ghép audio")
    log += "[1/3] GHÉP AUDIO\n"
    merged_wav = os.path.join(chapter_dir, f"{prefix}_merged.wav")
    concat_with_silence(ffmpeg, wav_files, silence_dur, merged_wav)
    log += f"✅ Ghép {len(wav_files)} file, silence={silence_dur}s\n"

    final_audio = merged_wav
    if bgm_path and os.path.isfile(bgm_path):
        if progress_cb: progress_cb(0.25, "đang trộn nhạc nền")
        log += f"\n🎵 TRỘN BGM (volume: {bgm_volume})\n"
        bgm_wav = os.path.join(chapter_dir, f"{prefix}_final.wav")
        mix_bgm(ffmpeg, merged_wav, bgm_path, bgm_wav, bgm_volume)
        final_audio = bgm_wav
        log += "✅ Đã trộn nhạc nền\n"

    if progress_cb: progress_cb(0.4, "đang tạo phụ đề")
    log += "\n[2/3] TẠO PHỤ ĐỀ (từ text gốc)\n"
    text_save_path = os.path.join(chapter_dir, f"{prefix}.txt")
    if not os.path.isfile(text_save_path):
        with open(text_save_path, "w", encoding="utf-8") as tf:
            tf.write(text)
    srt_path = generate_srt(chapter_dir, text_save_path, silence_dur, max_chars=60)
    if not srt_path:
        raise RuntimeError("Lỗi tạo phụ đề.")
    log += f"✅ Đã tạo: {os.path.basename(srt_path)}\n"

    if not bg_image_path:
        log += "\n⚠️ Chưa có ảnh nền → dừng ở bước audio + subtitle (không tạo video).\n"
        if progress_cb: progress_cb(1.0, "xong (chưa có video)")
        return chapter_dir, prefix, log, None

    if progress_cb: progress_cb(0.5, "đang render video (tự dò encoder)")
    log += "\n[3/3] RENDER VIDEO\n"
    out_mp4 = os.path.join(chapter_dir, f"{prefix}_video.mp4")
    used_encoder = render_video(final_audio, bg_image_path, srt_path, out_mp4, font_size=font_size)

    if not os.path.isfile(out_mp4):
        raise RuntimeError("Lỗi render video. Kiểm tra log FFmpeg.")
    size_mb = os.path.getsize(out_mp4) / (1024 * 1024)
    log += f"✅ Video: {os.path.basename(out_mp4)} ({size_mb:.1f} MB) — encoder: {used_encoder}\n"
    if progress_cb: progress_cb(1.0, "hoàn tất")
    return chapter_dir, prefix, log, out_mp4

def _process_chapter_e2e(text_file_path, bgm_path, bgm_volume, silence_dur, bg_image_path, font_size,
                          render_cb=None, pp_cb=None):
    """Chạy trọn 1 chương: Bước 3 (render audio) nối liền Bước 4 (hậu kỳ + video),
    không cần thao tác tay giữa 2 bước. Tự bỏ qua nếu chương đã xong từ trước.

    Trả về (prefix, log, video_path_or_None, da_bo_qua, khong_tim_thay_tieu_de_chuong).
    """
    with open(text_file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    text_norm = normalize_text_for_tts(raw_text)
    prefix, chapter_dir, chapter_num = _chapter_dir_for(text_norm, source_path=text_file_path)
    no_heading = chapter_num is None
    want_video = bool(bg_image_path)

    if _is_chapter_complete(chapter_dir, prefix, want_video):
        existing = os.path.join(chapter_dir, f"{prefix}_video.mp4") if want_video else None
        return prefix, f"⏭️ {prefix}: đã xử lý xong từ trước, bỏ qua.\n", existing, True, no_heading

    _, _, render_log, _, _ = _render_chapter_audio(text_file_path, progress_cb=render_cb)
    _, _, pp_log, video_path = _run_postprocess_core(
        text_file_path, bgm_path, bgm_volume, silence_dur, bg_image_path, font_size, progress_cb=pp_cb
    )
    return prefix, render_log + "\n" + pp_log, video_path, False, no_heading

def scan_output_health():
    """Quét toàn bộ outputs/ và báo cáo chương nào đang THIẾU file — để phát
    hiện NGAY những chương dở dang (như sự cố chương 1990 trước đây: có audio
    nhưng thiếu hẳn phụ đề/video vì hậu kỳ bị gián đoạn giữa chừng), thay vì
    tình cờ phát hiện ra sau này. "Chưa có video" một mình KHÔNG bị tính là
    lỗi (có thể do cố ý không dùng ảnh nền) — chỉ thiếu audio/phụ đề/text gốc
    mới được coi là vấn đề thật sự.
    """
    if not os.path.isdir(OUTPUT_DIR):
        return "⚠️ Chưa có thư mục outputs/ — chưa render chương nào."

    rows = []
    for name in sorted(os.listdir(OUTPUT_DIR)):
        chapter_dir = os.path.join(OUTPUT_DIR, name)
        if not os.path.isdir(chapter_dir):
            continue
        files = os.listdir(chapter_dir)
        parts = [f for f in files if re.match(rf"^{re.escape(name)}_c\d+_p\d+\.wav$", f)]
        has_txt = f"{name}.txt" in files
        has_merged = f"{name}_merged.wav" in files
        srt_path = os.path.join(chapter_dir, f"{name}_merged.srt")
        has_srt = os.path.isfile(srt_path) and os.path.getsize(srt_path) > 0
        video_path = os.path.join(chapter_dir, f"{name}_video.mp4")
        has_video = os.path.isfile(video_path) and os.path.getsize(video_path) > 0

        issues = []
        if not parts:
            issues.append("không có file audio nào")
        if parts and not has_merged:
            issues.append("chưa ghép audio (thiếu _merged.wav)")
        if parts and not has_srt:
            issues.append("thiếu phụ đề .srt — hậu kỳ có thể đã bị gián đoạn")
        if not has_txt:
            issues.append("thiếu text gốc .txt — không thể tạo lại phụ đề nếu cần")

        rows.append((name, len(parts), has_video, issues))

    if not rows:
        return "⚠️ outputs/ chưa có chương nào."

    bad = [r for r in rows if r[3]]
    report = f"🩺 KIỂM TRA {len(rows)} CHƯƠNG trong outputs/\n"
    report += f"✅ {len(rows) - len(bad)} chương ổn (đủ audio + phụ đề)\n"
    if bad:
        report += f"⚠️ {len(bad)} chương CÓ VẤN ĐỀ:\n"
        for name, n_parts, has_video, issues in bad:
            report += f"  • {name} ({n_parts} phần audio, {'có' if has_video else 'chưa có'} video): {', '.join(issues)}\n"
    else:
        report += "🎉 Không có chương nào thiếu file!\n"
    return report

def process_batch(input_files, bgm_file, bgm_volume, silence_dur, bg_image, font_size,
                   progress=gr.Progress(track_tqdm=False)):
    """Handler cho nút Batch: nhận nhiều file .txt, chạy Bước 3 -> Bước 4 liên tục
    cho từng chương, tự bỏ qua chương đã xong, và KHÔNG dừng cả batch nếu 1
    chương bị lỗi — để có thể để máy chạy qua đêm không cần trông chừng."""
    if selected_voice is None:
        return "❌ Chưa chọn giọng. Quay lại Bước 1.", []
    if not input_files:
        return "❌ Chưa chọn file nào.", []

    bgm_path = bgm_file.name if (bgm_file and hasattr(bgm_file, 'name')) else bgm_file
    img_path = bg_image.name if (bg_image and hasattr(bg_image, 'name')) else bg_image

    # Sắp xếp theo tên file để thứ tự chạy dễ đoán (vd. chương thấp -> cao).
    file_paths = sorted(f.name for f in input_files)
    total_files = len(file_paths)

    full_log = f"🌙 BATCH: {total_files} file — chương đã xong sẽ tự động được bỏ qua.\n\n"
    videos, n_done, n_skipped, n_failed, n_no_heading = [], 0, 0, 0, 0

    for idx, fp in enumerate(file_paths):
        label = os.path.basename(fp)

        def render_cb(done, total, desc, _idx=idx, _label=label):
            local = (done / total) if total else 0
            progress((_idx + local * 0.5) / total_files, desc=f"[{_idx+1}/{total_files}] {_label}: {desc}")

        def pp_cb(frac, desc, _idx=idx, _label=label):
            progress((_idx + 0.5 + frac * 0.5) / total_files, desc=f"[{_idx+1}/{total_files}] {_label}: {desc}")

        progress(idx / total_files, desc=f"[{idx+1}/{total_files}] Bắt đầu {label}...")
        try:
            prefix, chap_log, video_path, skipped, no_heading = _process_chapter_e2e(
                fp, bgm_path, bgm_volume, silence_dur, img_path, font_size,
                render_cb=render_cb, pp_cb=pp_cb,
            )
            full_log += f"=== {prefix} ({label}) ===\n{chap_log}\n"
            n_skipped += int(skipped)
            n_done += int(not skipped)
            n_no_heading += int(no_heading)
            if video_path:
                videos.append(video_path)
        except FileNotFoundError:
            n_failed += 1
            full_log += f"=== ❌ {label}: FFmpeg chưa cài. Chạy: winget install Gyan.FFmpeg rồi khởi động lại. ===\n\n"
        except Exception as e:
            n_failed += 1
            full_log += f"=== ❌ {label}: LỖI — {e} ===\n\n"

    progress(1.0, desc="Hoàn tất batch!")
    full_log += f"\n🎉 BATCH XONG: {n_done} chương mới, {n_skipped} bỏ qua (đã có sẵn), {n_failed} lỗi / tổng {total_files}."
    if n_no_heading:
        full_log += f"\n⚠️ {n_no_heading} file không có \"Chương N\"/\"Chapter N\" trong văn bản (xem chi tiết ở trên)."
    full_log += "\n\n" + scan_output_health()
    return full_log, videos

# ===== GIAO DIỆN GRADIO =====
with gr.Blocks(title="VieNeu-TTS Auto Reader", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🦜 VieNeu-TTS — Sản xuất Audiobook tự động")
    gr.Markdown("**Quy trình khép kín:** Chọn giọng → Nghe mẫu → Batch: Audio → Video (chạy liên tục, tự bỏ qua chương đã xong)")

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

        # ========== BƯỚC 3: BATCH — RENDER AUDIO -> VIDEO TỰ ĐỘNG ==========
        with gr.Tab("③ Render → Video (Batch)", id=2):
            gr.Markdown("### Upload nhiều file .txt chương truyện — render audio, ghép, tạo phụ đề và xuất video cho từng chương liên tục, không cần thao tác giữa chừng.")
            gr.Markdown("*Chương đã xử lý xong (đã có video, hoặc đã có audio+phụ đề nếu không dùng ảnh nền) sẽ tự động được bỏ qua ở lần chạy sau — an toàn để bấm chạy lại hoặc để máy chạy qua đêm.*")

            batch_input_files = gr.File(
                label="File(s) chương truyện (.txt) — có thể chọn nhiều file cùng lúc",
                file_types=[".txt"], file_count="multiple",
            )

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("#### 📂 Ảnh nền video")
                    batch_bg_image = gr.File(
                        label="🖼️ Ảnh nền (jpg/png, dùng chung cho mọi chương). Để trống = chỉ render audio + phụ đề, không tạo video.",
                        file_types=[".jpg", ".jpeg", ".png"],
                    )
                with gr.Column(scale=1):
                    gr.Markdown("#### ⚙️ Tuỳ chỉnh (dùng chung cho mọi chương)")
                    batch_bgm = gr.File(label="🎵 Nhạc nền BGM (tuỳ chọn)", file_types=[".mp3", ".wav"])
                    batch_bgm_vol = gr.Slider(label="Âm lượng BGM", minimum=0.01, maximum=0.2, value=0.05, step=0.01)
                    batch_silence = gr.Slider(label="Khoảng lặng giữa các phần (giây)", minimum=0.1, maximum=3.0, value=0.5, step=0.1)
                    batch_font = gr.Slider(label="Cỡ chữ phụ đề", minimum=14, maximum=40, value=24, step=1)

            btn_batch = gr.Button("🌙 Chạy Batch: Audio → Video cho tất cả file", variant="primary", size="lg")
            batch_log = gr.Textbox(label="Nhật ký Batch", lines=20, interactive=False)
            gr.Markdown("---")
            gr.Markdown("### 🎥 Video đã hoàn thành")
            batch_videos = gr.File(label="Tải video (.mp4)", file_count="multiple", interactive=False)

            btn_batch.click(
                fn=process_batch,
                inputs=[batch_input_files, batch_bgm, batch_bgm_vol, batch_silence, batch_bg_image, batch_font],
                outputs=[batch_log, batch_videos]
            )

            gr.Markdown("---")
            with gr.Accordion("🩺 Kiểm tra sức khoẻ toàn bộ outputs/ (chương nào đang thiếu file)", open=False):
                gr.Markdown("*Quét lại mọi chương đã từng render — kể cả những chương KHÔNG có trong lần chạy batch này — để phát hiện chương còn thiếu audio/phụ đề (báo cáo này cũng tự chạy sau mỗi lần Batch ở trên).*")
                btn_health = gr.Button("🩺 Kiểm tra ngay", variant="secondary")
                health_report = gr.Textbox(label="Báo cáo", lines=12, interactive=False)
                btn_health.click(fn=scan_output_health, outputs=[health_report])

if __name__ == "__main__":
    app.launch()
