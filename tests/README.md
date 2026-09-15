# VoxDirector AI — Testing Directory

This directory holds **VoxDirector AI's own** test suites — the multi-agent
audiobook/video pipeline built on top of the `vieneu` SDK. The SDK's own
test suite (testing the `vieneu` package itself) lives separately at
[`engine/sdk/`](../engine/sdk/) — see that folder's own README.

## How to run

```bash
uv run pytest tests/
```

(Running plain `uv run pytest` from the repo root discovers both this
folder and `engine/sdk/` — there is no `testpaths` restriction in
`pyproject.toml`. Use `pytest tests/` specifically when you only want
VoxDirector's own suite.)

## Test files

- **[test_llm_client.py](test_llm_client.py)** — Gemini model resolution/fallback (`voxdirector/llm_client.py`).
- **[test_punctuation_pauses.py](test_punctuation_pauses.py)** — punctuation → pause-duration table lookup (`pipeline/punctuation_pauses.py`, spec Section 7.3).
- **[test_audio_postprocess_variable_silence.py](test_audio_postprocess_variable_silence.py)** — per-boundary variable silence concatenation (`pipeline/audio_postprocess.py`, spec Section 7.2).
