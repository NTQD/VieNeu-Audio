# Backend that (Step 9+15 cua build order, Section 12 cua spec).
# Build context PHAI la goc repo (khong phai backend/) vi image can copy ca
# voxdirector/, pipeline/, data/ - xem docker-compose.yml o goc repo.
FROM python:3.12-slim

# ffmpeg: audio_postprocess.py (ghep/silence). espeak-ng: TAM THOI GIU LAI
# tu luc dung Piper (phonemizer cua Piper can lib nay o runtime) - Piper da
# bi go bo 2026-09-11, chua xac nhan VieNeu-TTS co can espeak-ng hay khong.
# Xem lai apt package list nay sau khi Step 2 (wiring VieNeu-TTS theo README
# chinh thuc) xac dinh dependency he thong that su can.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# QUAN TRONG: sentence-transformers (dung cho glossary embedding, chi can
# CPU - khong bao gio dung GPU trong container nay) keo theo torch nhu
# dependency bac cau. pip install torch mac dinh tren Linux/PyPI se cai ban
# CUDA (keo theo vai GB goi nvidia_* - nvidia-cusparselt, nvidia-nccl...)
# du server khong co GPU - xac nhan co THAT qua build image nay (2026-09-10):
# dung luong tai ve nhay vot len hang tram MB/goi CUDA. Cai ban CPU-only
# TRUOC de pip khong con can resolve/tai ban CUDA khi cai
# sentence-transformers sau do.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY voxdirector /app/voxdirector
COPY pipeline /app/pipeline
COPY data /app/data
COPY scripts /app/scripts
COPY backend/app /app/backend/app
# COPY cho voice model files (Piper .onnx da bi xoa 2026-09-11) se quay lai
# day khi Step 2 xac dinh VieNeu-TTS luu voice preset o dau.

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV PYTHONPATH=/app

WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
