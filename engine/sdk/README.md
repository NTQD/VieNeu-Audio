# VieNeu-TTS Testing Directory

This directory contains test suites and utilities for verifying the `vieneu`
SDK package itself (the upstream TTS engine this repo also hosts). It is
separate from [`tests/`](../../tests/), which holds VoxDirector AI's own
test suite for the application built on top of the SDK.

## How to run tests

Ensure you are in the project root:

```bash
uv run pytest engine/sdk/
```

(Plain `uv run pytest` from the repo root discovers both this folder and
`tests/`.)

---

### Individual Test Suites
- **[test_engine_standard.py](test_engine_standard.py)**: Tests for the standard VieNeuTTS engine (Torch/GGUF).
- **[test_engine_remote.py](test_engine_remote.py)**: Tests for the Remote API engine.
- **[test_engine_fast.py](test_engine_fast.py)**: Tests for the Fast (LMDeploy) engine.
- **[test_factory.py](test_factory.py)**: Tests for the Vieneu factory class.
- **[test_utils.py](test_utils.py)**: Tests for audio and text processing utilities.

---

### Other Utilities
- **[benchmark.py](benchmark.py)**: RTF and latency benchmarking.
