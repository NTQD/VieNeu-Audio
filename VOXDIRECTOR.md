# VoxDirector AI — where things live

This repo hosts two unrelated things: the **`vieneu`** PyPI package (Vietnamese
TTS SDK — `src/`, `apps/`, `examples/`, `finetune/`, `client/`, `sdk-deploy/`,
`engine/sdk/`, its own `README*.md`) and **VoxDirector AI**, the multi-agent
audiobook/video pipeline built on top of it. This file is just a map of the
latter, since it touches many top-level folders and can look like clutter
without one.

| Path | What it is |
|---|---|
| `voxdirector/` | Agents (Alpha/Beta/Gamma), config, LLM client, glossary |
| `pipeline/` | Text/audio processing: splitter, normalizer, postprocess, subtitles |
| `backend/` | FastAPI backend (real wiring — Alpha→Beta→TTS→postprocess→QA) |
| `frontend/` | Next.js UI |
| `data/` | Team-editable JSON config: voice presets, emotion lexicon, glossary seed, punctuation pauses |
| `deploy/` | nginx config + deployment notes for the Docker Compose stack |
| `docker-compose.yml` | `docker compose up` — brings up backend+frontend+nginx (stays at repo root; Compose looks for it there by convention) |
| `docs/voxdirector/` | Spec, user manual, running instructions, manual test checklist — current reference docs only |
| `docs/voxdirector/handoffs/` | Dated end-of-session handoff logs and the original architecture review — historical record, not current reference |
| `tests/` | VoxDirector's own pytest suite (LLM client, punctuation pauses, variable-silence postprocess) |
| `scratch_check/verified/` | Standalone dev scripts for build-order steps that have actually been run to a conclusion |
| `scratch_check/unverified/` | Standalone dev scripts that are written but not yet run/confirmed — check here before trusting a claim that depends on one |
| `scratch_check/manual_test_samples/`, `scratch_check/out/` | Shared fixtures/output for the scripts above, used by both `verified/` and `unverified/` |

Two folders belong to the `vieneu` SDK but are named/organized to make that
obvious rather than left ambiguous:

- `engine/sdk/` — the SDK's own pytest suite (testing `vieneu`/`vieneu_utils`
  themselves, not VoxDirector). Separate from `tests/` above on purpose.
- `sdk-deploy/` — the SDK's own Docker Compose configs (LMDeploy serve
  profile, GPU production image). Renamed from the former `docker/` so it's
  never confused with VoxDirector's own `docker-compose.yml` at repo root —
  these are two unrelated Docker setups for two unrelated things.

Everything else at the repo root (`src/`, `apps/`, `examples/`, `finetune/`,
`client/`, `config.yaml`, `run_xpu.bat`, etc.) belongs to the `vieneu`
package and wasn't touched by VoxDirector's cleanup — its layout is
load-bearing for the published package (`pyproject.toml` points at `src/`),
so it's left as-is.
