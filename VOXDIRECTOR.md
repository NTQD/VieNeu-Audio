# VoxDirector AI — where things live

This repo hosts two unrelated things: the **`vieneu`** PyPI package (Vietnamese
TTS SDK — `src/`, `apps/`, `examples/`, `finetune/`, `client/`, `docker/`,
its own `README*.md`) and **VoxDirector AI**, the multi-agent audiobook/video
pipeline built on top of it. This file is just a map of the latter, since it
touches many top-level folders and can look like clutter without one.

| Path | What it is |
|---|---|
| `voxdirector/` | Agents (Alpha/Beta/Gamma), config, LLM client, glossary |
| `pipeline/` | Text/audio processing: splitter, normalizer, postprocess, subtitles |
| `backend/` | FastAPI backend (real wiring — Alpha→Beta→TTS→postprocess→QA) |
| `frontend/` | Next.js UI |
| `data/` | Team-editable JSON config: voice presets, emotion lexicon, glossary seed, punctuation pauses |
| `deploy/` | nginx config + deployment notes for the Docker Compose stack |
| `docker-compose.yml` | `docker compose up` — brings up backend+frontend+nginx (stays at repo root; Compose looks for it there by convention) |
| `docs/voxdirector/` | Spec, user manual, running instructions, manual test checklist |
| `scratch_check/` | Standalone test/verification scripts written during development (not part of the app) |

Everything else at the repo root belongs to the `vieneu` package and wasn't
touched by VoxDirector's cleanup — its layout is load-bearing for the
published package (`pyproject.toml` points at `src/`), so it's left as-is.
