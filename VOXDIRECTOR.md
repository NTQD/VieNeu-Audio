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
| `docker-compose.gpu.yml` | GPU override for the above (`-f docker-compose.yml -f docker-compose.gpu.yml up -d`) — also VoxDirector's own, not the SDK's; see `docs/voxdirector/RUNNING_GPU.md` |
| `docs/voxdirector/` | Spec, user manual, running instructions, manual test checklist — current reference docs only |
| `docs/voxdirector/handoffs/` | Dated end-of-session handoff logs and the original architecture review — historical record, not current reference |
| `tests/` | VoxDirector's own pytest suite (LLM client, punctuation pauses, variable-silence postprocess) |
| `scratch_check/verified/` | Standalone dev scripts for build-order steps that have actually been run to a conclusion |
| `scratch_check/unverified/` | Standalone dev scripts that are written but not yet run/confirmed — check here before trusting a claim that depends on one. Created on demand; may not exist if empty (nothing unverified right now, 2026-09-15). |
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

## Root-level loose files — audited 2026-09-15, mostly pinned there on purpose

Every tracked file directly at the repo root was checked against what
actually reads it before concluding it was "clutter." Almost all of it
turned out to be genuinely pinned to root by tool convention or a hardcoded
path, not just left lying around:

- `.dockerignore`, `.env.example`, `.gitignore`, `.python-version`,
  `pyproject.toml`, `uv.lock`, `Makefile`, `LICENSE` — standard tool/ecosystem
  root conventions (git, uv, make, PyPI packaging).
- `README.md`, `README.vi.md`, `README_PYPI.md` — `pyproject.toml`'s
  `readme = "README_PYPI.md"` field is a literal relative path; GitHub only
  auto-renders a root `README.md`; keeping the Vietnamese translation
  alongside is the normal i18n-README convention, not a placement mistake.
- `config.yaml` — hardcoded root-relative path in `apps/gradio_main.py` /
  `apps/gradio_xpu.py` (`os.path.join(dirname(dirname(__file__)), "config.yaml")`).
  Moving it means editing those SDK app files for no real benefit.
- `run_xpu.bat`, `setup_xpu_uv.bat`, `requirements_xpu.txt` — the Intel-XPU
  dev-setup trio; self-relative (`cd /d %~dp0`) so technically movable, but
  a double-click launcher script belongs at the root where a user expects to
  find it.
- `docker-compose.yml`, `docker-compose.gpu.yml` — VoxDirector's own, listed
  in the table above.

**One file was found to be genuine dead weight and removed**:
`VieNeu_Audio_Colab.ipynb`. It was referenced nowhere in the repo — not even
by `README.md`'s own "Open In Colab" badge, which points at an
externally-hosted Google Drive copy instead — and its content was stale: it
imports `pipeline.auto_tts` (a module that no longer exists) and describes
the retired 4-agent "Alpha/Beta/Gamma/Delta" architecture from before the
Beta+Gamma merge in spec v4. Running it today would fail immediately.
