# VoxDirector AI — Running on a GPU machine (Windows)

Written for the specific machine confirmed via `nvidia-smi`: **NVIDIA GeForce
RTX 5050 (laptop)**, driver 595.79, CUDA 13.2, Windows, **8 GB VRAM**. If you
test on a different machine, the GPU/VRAM specifics below may not apply —
ask again with that machine's `nvidia-smi` output.

This is in addition to the normal [RUNNING.md](./RUNNING.md) — read that
first for `.env` setup and the basic 3-container flow. This guide only
covers the GPU-specific parts.

## One-time machine setup

1. **Docker Desktop → Settings → General**: confirm "Use the WSL 2 based
   engine" is checked.
2. **Docker Desktop → Settings → Resources**: confirm GPU support is
   enabled (recent Docker Desktop versions turn this on automatically when
   an NVIDIA driver with WSL2 CUDA support is detected — 595.79 qualifies).
3. Verify Docker can actually see the GPU:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
   ```
   This should print the same GPU table you saw with `nvidia-smi` directly.
   If it errors instead, Docker Desktop's GPU passthrough isn't set up yet —
   fix that before continuing (usually: update Docker Desktop to the latest
   version, restart it, and make sure WSL2 itself is up to date via
   `wsl --update` in a normal Windows terminal).

## Building and running with GPU support

Same as the normal flow, but pass **both** compose files (the base one plus
the GPU override) on every command:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
```

The first build takes a while — it downloads torch's CUDA-enabled build
(~2-3 GB) on top of the usual dependencies. Later runs reuse the cached
layers.

## Confirming GPU is actually being used

```bash
docker compose logs backend | grep "Thiết bị"
```

You're looking for:
```
[VoxDirector] Thiết bị được chọn: CUDA (torch.cuda.is_available()=True (NVIDIA GeForce RTX 5050 Laptop GPU))
```

If it instead says `CPU (không phát hiện được GPU...)`, something in the
GPU passthrough chain isn't connected — re-check the verification command
above, or check `docker compose logs backend` for a pip/torch install error
during the build.

## About your specific 8 GB VRAM

This is a tight budget once Windows itself (~2 GB was already in use in
your `nvidia-smi` output, before running anything) is accounted for — call
it ~6 GB actually usable. Two decisions were made accordingly:

- **Only VieNeu-TTS (voice synthesis) runs on GPU by default.** Agent
  Gamma's quality-check step (faster-whisper) is pinned to CPU
  (`VOXDIRECTOR_WHISPER_DEVICE=cpu`, already set in `backend/Dockerfile.gpu`)
  so the two don't compete for VRAM. TTS synthesis speed is the actual
  performance win you're testing for; Gamma is a one-off check per job, so
  CPU there costs you a few extra seconds, not a bottleneck.
- If you want to test full-GPU mode anyway (both TTS and Whisper on GPU),
  override it per run:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml \
    run -e VOXDIRECTOR_WHISPER_DEVICE=cuda backend
  ```
  Watch VRAM with `nvidia-smi` (run it again on a normal Windows terminal
  while a job is processing) — if you see out-of-memory errors in
  `docker compose logs backend`, that's the 8 GB budget being exceeded;
  drop back to the CPU-Whisper default.

Your GPU was also already sitting at 74°C at idle in the screenshot you
sent — worth keeping an eye on temps during a longer test run, especially
on a laptop chassis.

## Switching back to CPU mode

Just drop the `-f docker-compose.gpu.yml` part and rebuild:
```bash
docker compose up --build -d
```
