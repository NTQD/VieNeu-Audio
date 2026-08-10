# 🦜 VieNeu-Audio

**An automated audiobook & video production pipeline for Vietnamese long-form text, built on top of [VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS).**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built on VieNeu-TTS](https://img.shields.io/badge/Built%20on-VieNeu--TTS-blue)](https://github.com/pnnbao97/VieNeu-TTS)

**Languages:** [English](#english) | [Tiếng Việt](#tiếng-việt)

---

## English

VieNeu-Audio takes a plain-text chapter file and turns it into a finished, subtitled MP4 video: it normalizes numbers/units for correct pronunciation, splits the chapter into TTS-sized chunks, synthesizes speech with VieNeu-TTS, stitches the audio back together with configurable silence between paragraphs and chapters, optionally mixes in background music, generates subtitles synced to the actual rendered audio, and burns everything into a video over a background image — all through a Gradio app or a scriptable CLI.

### Credits & Acknowledgments

**This project is not a text-to-speech engine.** All speech synthesis is performed by **[VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS)**, created by **[Phạm Nguyễn Ngọc Bảo (pnnbao97)](https://github.com/pnnbao97)** — an advanced, open-source, on-device Vietnamese TTS model with instant voice cloning, released under the **Apache License 2.0**. VieNeu-Audio consumes it as a regular dependency (`pip install vieneu`) and does not vendor, modify, or redistribute any of its source code, model weights, or voice assets.

If you find this pipeline useful, please go star and support the original project:
- Repository: https://github.com/pnnbao97/VieNeu-TTS
- Models on Hugging Face: https://huggingface.co/pnnbao-ump
- License: [Apache License 2.0](https://github.com/pnnbao97/VieNeu-TTS/blob/main/LICENSE)

VieNeu-Audio itself only adds the *production pipeline* around the engine — chunking, normalization, audio assembly, subtitles, and video rendering. This project is an independent, community-built tool and is **not officially affiliated with or endorsed by** the VieNeu-TTS project.

### How it works

The pipeline is exposed as three tabs in the Gradio app (`pipeline/auto_tts.py`):

```
① Pick a voice          Load VieNeu-TTS preset voices and preview them, or
        │                 clone a voice from a short reference clip
        │                 (encode_reference) and preview the clone.
        │
② Preview a sample       Render a longer test phrase (numbers, units,
        │                 proper nouns) to stress-test the chosen voice
        │                 before committing to a full batch.
        │
③ Render → Video (Batch) Upload one or many chapter .txt files at once.
                          For each: normalize → split into ~250-word
                          chunks → synthesize in GPU-batched groups →
                          concatenate with configurable silence (longer
                          gap between detected chapters, shorter between
                          paragraphs) → optionally mix in background
                          music → generate an .srt whose timestamps are
                          derived from the *actual* rendered audio
                          duration of each chunk → burn image + audio +
                          subtitles into an .mp4 (or skip the burn-in and
                          keep the .srt separate for YouTube's native
                          caption upload). Chapters that already have
                          complete output are skipped automatically, so
                          it's safe to re-run a batch after an interrupted
                          session — nothing is re-rendered from scratch.
```

A built-in health-check scans `outputs/` for any chapter left in a partial state (e.g. audio rendered but subtitles/video missing from an interrupted run) and reports it.

#### Module breakdown

| File | Responsibility |
|---|---|
| [`pipeline/text_normalizer.py`](pipeline/text_normalizer.py) | Rewrites numbers, decimals, percentages, units (km, kg, m²...), fractions, exponents, and numeric ranges into spoken Vietnamese words so the TTS engine pronounces them correctly instead of reading digit-by-digit. |
| [`pipeline/text_splitter.py`](pipeline/text_splitter.py) | Splits normalized text into sentence-aligned chunks capped at a configurable word count (default 250), so each chunk stays within a comfortable TTS generation length. |
| [`pipeline/auto_tts.py`](pipeline/auto_tts.py) | The Gradio application. Orchestrates voice selection/cloning, sample preview, and batch chapter rendering + post-production across multiple uploaded files; auto-detects chapter numbers from a `Chương N` / `Chapter N` heading to name output folders, skips chapters already fully rendered, and includes an output health-check report. |
| [`pipeline/audio_postprocess.py`](pipeline/audio_postprocess.py) | FFmpeg-based concatenation of per-chunk `.wav` files with inserted silence, and background-music mixing at a configurable volume. |
| [`pipeline/subtitle_generator.py`](pipeline/subtitle_generator.py) | Builds an `.srt` by pairing each text chunk with the measured duration of its corresponding rendered `.wav`, weighting per-line timing by character count so subtitle pacing matches the real audio. |
| [`pipeline/video_renderer.py`](pipeline/video_renderer.py) | Renders a static background image + final audio + optional burned-in subtitles into an `.mp4` via FFmpeg, auto-detecting the best available H.264 encoder (NVIDIA NVENC → Intel Quick Sync → libx264 CPU fallback). |
| [`pipeline/make_video.py`](pipeline/make_video.py) | A CLI entry point that runs the full post-production chain (concat → subtitles → video) against an already-rendered chapter folder, without the Gradio UI. |

Every chapter's outputs are written to `outputs/<chapter_id>/` (auto-named from a detected `Chương N` heading, e.g. `outputs/C_1847/`), keeping the source text, every audio chunk, the merged track, subtitles, and final video together per chapter.

### Installation

**Prerequisites:**
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) available on your `PATH` (or in a standard install location — the launcher searches common Windows install paths automatically)

```bash
git clone https://github.com/NTQD/VieNeu-Audio.git
cd VieNeu-Audio
pip install -r requirements.txt
```

> `requirements.txt` installs [`vieneu`](https://pypi.org/project/vieneu/) (the VieNeu-TTS SDK, from PyPI) and `gradio`. See the [VieNeu-TTS README](https://github.com/pnnbao97/VieNeu-TTS#readme) for GPU-accelerated install options.

### Usage

**Gradio app (recommended):**

```bash
python run_app.py
# or, on Windows:
run.bat
```

Walk through the tabs in order: pick (or clone) a voice, preview a sample, then in Step ③ upload one or many chapter `.txt` files and run the batch — each chapter is rendered, post-processed, and (if you supplied a background image) exported to `.mp4` in sequence, with completed chapters skipped automatically on re-runs.

**CLI (for scripting/automation), once a chapter's audio has already been rendered via Step ③:**

```bash
python pipeline/make_video.py outputs/C_1847 background.png --bgm ambient.mp3 --silence 0.5 --font 24
```

#### Running on Google Colab

If your own machine is slow, `VieNeu_Audio_Colab.ipynb` runs the same Gradio app on a free Colab runtime instead — no GPU required (voice synthesis uses a CPU-friendly quantized backbone by default), but Colab's CPU is typically faster than an underpowered laptop, and there's no local install to manage:

1. Upload `VieNeu_Audio_Colab.ipynb` to [Google Colab](https://colab.research.google.com/) (**File → Upload notebook**).
2. Run the cells top to bottom:
   - **Mount Google Drive** — code and every chapter's output are stored under `MyDrive/VieNeu-Audio/`, so nothing is lost if the runtime disconnects.
   - **Upload code** — the first time, zip this repo's `pipeline/` folder and upload it when prompted (skip this step on later runs, since it's already saved in Drive).
   - **Install dependencies** — `ffmpeg`, a Vietnamese-capable font, and the Python packages.
   - **Quick check** — confirms an H.264 encoder and the Vietnamese font are available.
   - **Launch** — starts the Gradio app and prints a `https://xxxxx.gradio.live` link; open it and use the app exactly like the local version.
3. If the session disconnects (Colab free tier idles out after ~90 minutes of inactivity), reconnect, re-run the Drive-mount and launch cells, and resume — chapters that finished rendering before the disconnect are detected and skipped.

### Current limitations

- Chapter detection relies on the source text containing a `Chương N` / `Chapter N` heading; text without one falls back to a generic output folder named after the source file.
- Subtitle timing is a character-count-weighted estimate against each chunk's rendered audio duration, not true forced alignment — pacing is close but not frame-exact.

### Content responsibility

This tool does not include, generate, or distribute any narrative text, background art, or media of its own — you supply your own source text and images. You are solely responsible for ensuring you have the necessary rights to any text, images, or music you process with this pipeline, and for how you distribute the resulting audio/video.

### License

VieNeu-Audio is released under the [MIT License](LICENSE). It depends on, but does not redistribute, the Apache-2.0-licensed `vieneu` package — see [Credits & Acknowledgments](#credits--acknowledgments) above.

---

## Tiếng Việt

VieNeu-Audio nhận một file văn bản thuần (.txt) chứa nội dung chương truyện và biến nó thành một video MP4 hoàn chỉnh, có phụ đề: chuẩn hoá số/đơn vị để đọc đúng, chia chương thành các đoạn vừa với TTS, tổng hợp giọng nói bằng VieNeu-TTS, ghép audio lại với khoảng lặng có thể tuỳ chỉnh giữa các đoạn/chương, tuỳ chọn trộn nhạc nền, tạo phụ đề khớp với thời lượng audio thực tế, và ghép tất cả thành video trên nền ảnh — tất cả qua giao diện Gradio hoặc dòng lệnh (CLI).

### Ghi công & Lời cảm ơn

**Dự án này KHÔNG phải là một công cụ tổng hợp giọng nói (TTS engine).** Toàn bộ việc tổng hợp giọng nói do **[VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS)** thực hiện, được tạo bởi **[Phạm Nguyễn Ngọc Bảo (pnnbao97)](https://github.com/pnnbao97)** — một mô hình TTS tiếng Việt mã nguồn mở, chạy on-device, hỗ trợ nhân bản giọng tức thời, phát hành theo **Giấy phép Apache 2.0**. VieNeu-Audio chỉ sử dụng nó như một dependency thông thường (`pip install vieneu`) và không đóng gói lại, chỉnh sửa, hay phân phối lại bất kỳ mã nguồn, trọng số mô hình, hay dữ liệu giọng nói nào của dự án gốc.

Nếu bạn thấy pipeline này hữu ích, hãy star và ủng hộ dự án gốc:
- Repository: https://github.com/pnnbao97/VieNeu-TTS
- Model trên Hugging Face: https://huggingface.co/pnnbao-ump
- Giấy phép: [Apache License 2.0](https://github.com/pnnbao97/VieNeu-TTS/blob/main/LICENSE)

VieNeu-Audio chỉ bổ sung phần *pipeline sản xuất* xung quanh engine đó — chia đoạn, chuẩn hoá văn bản, ghép audio, tạo phụ đề, và render video. Đây là một công cụ độc lập do cộng đồng xây dựng, **không thuộc và không được xác nhận chính thức bởi** dự án VieNeu-TTS.

### Cách hoạt động

Pipeline được chia thành 3 tab trong ứng dụng Gradio (`pipeline/auto_tts.py`):

```
① Chọn giọng             Tải danh sách giọng preset của VieNeu-TTS và nghe
        │                 thử, hoặc nhân bản giọng từ 1 đoạn audio mẫu
        │                 ngắn (encode_reference) rồi nghe thử giọng nhân bản.
        │
② Nghe bản mẫu            Đọc thử 1 câu dài (chứa số, đơn vị, tên riêng) để
        │                 kiểm tra kỹ khả năng đọc của giọng đã chọn trước
        │                 khi chạy cả batch.
        │
③ Render → Video (Batch)  Upload 1 hoặc nhiều file .txt chương truyện cùng
                          lúc. Với mỗi chương: chuẩn hoá → chia thành các
                          đoạn ~250 từ → tổng hợp giọng theo LÔ (GPU-batch)
                          → ghép các đoạn với khoảng lặng tuỳ chỉnh (dài hơn
                          giữa các chương, ngắn hơn giữa các đoạn) → tuỳ
                          chọn trộn nhạc nền → tạo phụ đề .srt với thời gian
                          lấy từ THỜI LƯỢNG THỰC TẾ của audio đã render →
                          ghép ảnh nền + audio + phụ đề thành video .mp4
                          (hoặc bỏ qua bước ghi cứng phụ đề, giữ riêng file
                          .srt để tự upload lên YouTube). Chương nào đã xử
                          lý xong sẽ tự động được bỏ qua ở lần chạy sau — an
                          toàn để chạy lại batch sau khi bị gián đoạn giữa
                          chừng, không phải render lại từ đầu.
```

Có sẵn tính năng kiểm tra sức khoẻ (health-check) quét thư mục `outputs/` để phát hiện chương nào đang dở dang (vd. đã có audio nhưng thiếu phụ đề/video do bị gián đoạn giữa chừng) và báo cáo lại.

#### Chi tiết từng module

| File | Chức năng |
|---|---|
| [`pipeline/text_normalizer.py`](pipeline/text_normalizer.py) | Chuyển số, số thập phân, phần trăm, đơn vị đo (km, kg, m²...), phân số, luỹ thừa, và dải số thành chữ tiếng Việt để TTS đọc đúng thay vì đọc từng chữ số. |
| [`pipeline/text_splitter.py`](pipeline/text_splitter.py) | Chia văn bản đã chuẩn hoá thành các đoạn theo câu, giới hạn số từ (mặc định 250), để mỗi đoạn nằm trong độ dài phù hợp cho TTS. |
| [`pipeline/auto_tts.py`](pipeline/auto_tts.py) | Ứng dụng Gradio. Điều phối việc chọn/nhân bản giọng, nghe bản mẫu, và render batch nhiều chương + hậu kỳ; tự nhận diện số chương từ tiêu đề `Chương N` / `Chapter N` để đặt tên thư mục output, tự bỏ qua chương đã xử lý xong, và có báo cáo kiểm tra sức khoẻ output. |
| [`pipeline/audio_postprocess.py`](pipeline/audio_postprocess.py) | Ghép các file `.wav` từng đoạn bằng FFmpeg kèm khoảng lặng, và trộn nhạc nền ở mức âm lượng tuỳ chỉnh. |
| [`pipeline/subtitle_generator.py`](pipeline/subtitle_generator.py) | Tạo file `.srt` bằng cách ghép mỗi đoạn văn bản với thời lượng đo được của file `.wav` tương ứng, chia thời gian hiển thị mỗi dòng theo tỉ lệ số ký tự để khớp với audio thật hơn. |
| [`pipeline/video_renderer.py`](pipeline/video_renderer.py) | Render ảnh nền tĩnh + audio cuối + phụ đề (tuỳ chọn ghi cứng) thành video `.mp4` qua FFmpeg, tự dò encoder H.264 tốt nhất khả dụng (NVIDIA NVENC → Intel Quick Sync → libx264 chạy CPU). |
| [`pipeline/make_video.py`](pipeline/make_video.py) | Entry point dạng CLI, chạy trọn chuỗi hậu kỳ (ghép audio → tạo phụ đề → render video) trên 1 thư mục chương đã render sẵn, không cần giao diện Gradio. |

Toàn bộ output của mỗi chương được lưu tại `outputs/<chapter_id>/` (tự đặt tên từ tiêu đề `Chương N` phát hiện được, vd. `outputs/C_1847/`), gồm văn bản gốc, từng đoạn audio, track đã ghép, phụ đề, và video cuối cùng.

### Cài đặt

**Yêu cầu:**
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) có trong `PATH` (hoặc ở vị trí cài đặt chuẩn — launcher tự tìm các đường dẫn cài đặt phổ biến trên Windows)

```bash
git clone https://github.com/NTQD/VieNeu-Audio.git
cd VieNeu-Audio
pip install -r requirements.txt
```

> `requirements.txt` cài [`vieneu`](https://pypi.org/project/vieneu/) (SDK của VieNeu-TTS, từ PyPI) và `gradio`. Xem [README của VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS#readme) để biết các tuỳ chọn cài đặt tăng tốc bằng GPU.

### Sử dụng

**Ứng dụng Gradio (khuyến nghị):**

```bash
python run_app.py
# hoặc, trên Windows:
run.bat
```

Đi qua lần lượt các tab: chọn (hoặc nhân bản) giọng, nghe bản mẫu, rồi ở Bước ③ upload 1 hoặc nhiều file `.txt` chương truyện và chạy batch — mỗi chương sẽ được render, hậu kỳ, và (nếu có ảnh nền) xuất thành `.mp4` lần lượt, chương nào đã xong sẽ tự động được bỏ qua ở lần chạy sau.

**CLI (để tự động hoá/viết script), khi audio của 1 chương đã được render qua Bước ③:**

```bash
python pipeline/make_video.py outputs/C_1847 background.png --bgm ambient.mp3 --silence 0.5 --font 24
```

#### Chạy trên Google Colab

Nếu máy của bạn yếu, `VieNeu_Audio_Colab.ipynb` chạy cùng ứng dụng Gradio trên Colab miễn phí — không cần GPU (mặc định dùng backbone lượng tử hoá phù hợp CPU), nhưng CPU của Colab thường nhanh hơn 1 laptop yếu, và không cần cài đặt gì trên máy local:

1. Upload `VieNeu_Audio_Colab.ipynb` lên [Google Colab](https://colab.research.google.com/) (**File → Upload notebook**).
2. Chạy lần lượt từng cell:
   - **Gắn Google Drive** — code và output của mọi chương đều lưu tại `MyDrive/VieNeu-Audio/`, không mất khi mất kết nối.
   - **Upload code** — lần đầu, nén thư mục `pipeline/` của repo này thành zip rồi upload khi được yêu cầu (bỏ qua bước này ở các lần chạy sau, vì đã lưu sẵn trong Drive).
   - **Cài dependencies** — `ffmpeg`, font hỗ trợ tiếng Việt, và các gói Python.
   - **Kiểm tra nhanh** — xác nhận có encoder H.264 và font tiếng Việt khả dụng.
   - **Khởi chạy** — chạy ứng dụng Gradio và in ra link `https://xxxxx.gradio.live`; mở link đó và dùng ứng dụng y hệt bản local.
3. Nếu mất kết nối (Colab free tier tự ngắt sau ~90 phút không hoạt động), kết nối lại, chạy lại cell gắn Drive và cell khởi chạy, rồi tiếp tục — chương nào đã render xong trước khi mất kết nối sẽ tự động được phát hiện và bỏ qua.

### Hạn chế hiện tại

- Việc nhận diện chương phụ thuộc vào văn bản gốc có chứa tiêu đề `Chương N` / `Chapter N`; văn bản không có tiêu đề sẽ dùng tên thư mục output chung theo tên file nguồn.
- Thời gian hiển thị phụ đề là ước lượng theo tỉ lệ số ký tự so với thời lượng audio đã render của từng đoạn, không phải căn chỉnh cưỡng bức (forced alignment) thật sự — độ khớp gần đúng nhưng không chính xác tuyệt đối theo từng khung hình.

### Trách nhiệm về nội dung

Công cụ này không kèm theo, tạo ra, hay phân phối bất kỳ nội dung truyện, hình ảnh nền, hay media nào của riêng nó — bạn tự cung cấp văn bản nguồn và hình ảnh của mình. Bạn hoàn toàn chịu trách nhiệm đảm bảo có đủ quyền sử dụng đối với bất kỳ văn bản, hình ảnh, hay nhạc nào bạn xử lý bằng pipeline này, cũng như cách bạn phân phối audio/video kết quả.

### Giấy phép

VieNeu-Audio được phát hành theo [Giấy phép MIT](LICENSE). Dự án phụ thuộc vào, nhưng không phân phối lại, gói `vieneu` (giấy phép Apache-2.0) — xem [Ghi công & Lời cảm ơn](#ghi-công--lời-cảm-ơn) ở trên.
