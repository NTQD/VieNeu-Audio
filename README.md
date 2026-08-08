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

The pipeline is organized as four sequential stages, exposed as tabs in the Gradio app (`pipeline/auto_tts.py`):

```
① Pick a voice          Load VieNeu-TTS preset voices, select one.
        │
② Preview a sample       Render a short test phrase to confirm the voice
        │                 sounds right before committing to a full chapter.
        │
③ Render chapter audio   Upload a chapter .txt → normalize → split into
        │                 ~250-word chunks → synthesize each chunk → save
        │                 one .wav per chunk under outputs/<chapter>/.
        │
④ Post-production        Concatenate all chunk .wavs with configurable
                          silence (longer gap between detected chapters,
                          shorter gap between paragraphs) → optionally mix
                          in background music → generate an .srt whose
                          timestamps are derived from the *actual* rendered
                          audio duration of each chunk (not an estimate) →
                          burn image + audio + subtitles into an .mp4.
```

### Module breakdown

| File | Responsibility |
|---|---|
| [`pipeline/text_normalizer.py`](pipeline/text_normalizer.py) | Rewrites numbers, decimals, percentages, units (km, kg, m²...), fractions, exponents, and numeric ranges into spoken Vietnamese words so the TTS engine pronounces them correctly instead of reading digit-by-digit. |
| [`pipeline/text_splitter.py`](pipeline/text_splitter.py) | Splits normalized text into sentence-aligned chunks capped at a configurable word count (default 250), so each chunk stays within a comfortable TTS generation length. |
| [`pipeline/auto_tts.py`](pipeline/auto_tts.py) | The Gradio application. Orchestrates voice selection, sample preview, chapter rendering, and the post-production pipeline; auto-detects chapter numbers from a `Chương N` / `Chapter N` heading to name output folders. |
| [`pipeline/audio_postprocess.py`](pipeline/audio_postprocess.py) | FFmpeg-based concatenation of per-chunk `.wav` files with inserted silence, and background-music mixing at a configurable volume. |
| [`pipeline/subtitle_generator.py`](pipeline/subtitle_generator.py) | Builds an `.srt` by pairing each text chunk with the measured duration of its corresponding rendered `.wav`, so subtitle timing always matches the real audio rather than an estimate. |
| [`pipeline/video_renderer.py`](pipeline/video_renderer.py) | Renders a static background image + final audio + burned-in subtitles into an `.mp4` via FFmpeg. |
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

Walk through the four tabs in order: pick a voice, preview a sample, upload a chapter `.txt` to render audio, then run post-production (optionally with background music and a background image) to get a finished video.

**CLI (for scripting/automation), once a chapter's audio has already been rendered via Step ③:**

```bash
python pipeline/make_video.py outputs/C_1847 background.png --bgm ambient.mp3 --silence 0.5 --font 24
```

---

## Current limitations

- **Video encoding requires Intel Quick Sync Video** (`h264_qsv`) — [`video_renderer.py`](pipeline/video_renderer.py) currently hardcodes this encoder. It will fail on machines without Intel QSV hardware (including most cloud GPU runtimes). Swapping in `libx264` (CPU, universally available) or `h264_nvenc` (NVIDIA GPUs) is on the roadmap.
- Chapter detection relies on the source text containing a `Chương N` / `Chapter N` heading; text without one falls back to a generic output folder.
- Rendering does not currently resume from a partial run — an interrupted chapter render needs to be restarted from the first chunk.

## Content responsibility

This tool does not include, generate, or distribute any narrative text, background art, or media of its own — you supply your own source text and images. You are solely responsible for ensuring you have the necessary rights to any text, images, or music you process with this pipeline, and for how you distribute the resulting audio/video.

## License

VieNeu-Audio is released under the [MIT License](LICENSE). It depends on, but does not redistribute, the Apache-2.0-licensed `vieneu` package — see [Credits & Acknowledgments](#credits--acknowledgments) above.
