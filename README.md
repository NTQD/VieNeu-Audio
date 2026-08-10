# 🦜 VieNeu-Audio

**An automated audiobook & video production pipeline for Vietnamese long-form text, built on top of [VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS).**

VieNeu-Audio takes a plain-text chapter file and turns it into a finished, subtitled MP4 video: it normalizes numbers/units for correct pronunciation, splits the chapter into TTS-sized chunks, synthesizes speech with VieNeu-TTS, stitches the audio back together with configurable silence between paragraphs and chapters, optionally mixes in background music, generates subtitles synced to the actual rendered audio, and burns everything into a video over a background image — all through a 4-step Gradio wizard or a scriptable CLI.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built on VieNeu-TTS](https://img.shields.io/badge/Built%20on-VieNeu--TTS-blue)](https://github.com/pnnbao97/VieNeu-TTS)

---

## Credits & Acknowledgments

**This project is not a text-to-speech engine.** All speech synthesis is performed by **[VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS)**, created by **[Phạm Nguyễn Ngọc Bảo (pnnbao97)](https://github.com/pnnbao97)** — an advanced, open-source, on-device Vietnamese TTS model with instant voice cloning, released under the **Apache License 2.0**. VieNeu-Audio consumes it as a regular dependency (`pip install vieneu`) and does not vendor, modify, or redistribute any of its source code, model weights, or voice assets.

If you find this pipeline useful, please go star and support the original project:
- Repository: https://github.com/pnnbao97/VieNeu-TTS
- Models on Hugging Face: https://huggingface.co/pnnbao-ump
- License: [Apache License 2.0](https://github.com/pnnbao97/VieNeu-TTS/blob/main/LICENSE)

VieNeu-Audio itself only adds the *production pipeline* around the engine — chunking, normalization, audio assembly, subtitles, and video rendering. This project is an independent, community-built tool and is **not officially affiliated with or endorsed by** the VieNeu-TTS project.

---

## How it works

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

A built-in health-check scans `outputs/` for any chapter left in a partial
state (e.g. audio rendered but subtitles/video missing from an interrupted
run) and reports it.

### Module breakdown

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

---

## Installation

**Prerequisites:**
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) available on your `PATH` (or in a standard install location — the launcher searches common Windows install paths automatically)

```bash
git clone https://github.com/NTQD/VieNeu-Audio.git
cd VieNeu-Audio
pip install -r requirements.txt
```

> `requirements.txt` installs [`vieneu`](https://pypi.org/project/vieneu/) (the VieNeu-TTS SDK, from PyPI) and `gradio`. See the [VieNeu-TTS README](https://github.com/pnnbao97/VieNeu-TTS#readme) for GPU-accelerated install options.

## Usage

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

### Running on Google Colab

If your own machine is slow, `VieNeu_Audio_Colab.ipynb` runs the same Gradio app on a free Colab runtime instead — no GPU required (voice synthesis uses a CPU-friendly quantized backbone by default), but Colab's CPU is typically faster than an underpowered laptop, and there's no local install to manage:

1. Upload `VieNeu_Audio_Colab.ipynb` to [Google Colab](https://colab.research.google.com/) (**File → Upload notebook**).
2. Run the cells top to bottom:
   - **Mount Google Drive** — code and every chapter's output are stored under `MyDrive/VieNeu-Audio/`, so nothing is lost if the runtime disconnects.
   - **Upload code** — the first time, zip this repo's `pipeline/` folder and upload it when prompted (skip this step on later runs, since it's already saved in Drive).
   - **Install dependencies** — `ffmpeg`, a Vietnamese-capable font, and the Python packages.
   - **Quick check** — confirms an H.264 encoder and the Vietnamese font are available.
   - **Launch** — starts the Gradio app and prints a `https://xxxxx.gradio.live` link; open it and use the app exactly like the local version.
3. If the session disconnects (Colab free tier idles out after ~90 minutes of inactivity), reconnect, re-run the Drive-mount and launch cells, and resume — chapters that finished rendering before the disconnect are detected and skipped.

---

## Current limitations

- Chapter detection relies on the source text containing a `Chương N` / `Chapter N` heading; text without one falls back to a generic output folder named after the source file.
- Subtitle timing is a character-count-weighted estimate against each chunk's rendered audio duration, not true forced alignment — pacing is close but not frame-exact.

## Content responsibility

This tool does not include, generate, or distribute any narrative text, background art, or media of its own — you supply your own source text and images. You are solely responsible for ensuring you have the necessary rights to any text, images, or music you process with this pipeline, and for how you distribute the resulting audio/video.

## License

VieNeu-Audio is released under the [MIT License](LICENSE). It depends on, but does not redistribute, the Apache-2.0-licensed `vieneu` package — see [Credits & Acknowledgments](#credits--acknowledgments) above.
