# Container cho VoxDirector AI (VieNeu-Audio pipeline + 4 Agent) — deploy lên
# Cloud Run. Xem VoxDirectorAI_Technical_Spec.md Section 11 cho quy trình
# build/push/deploy đầy đủ.
#
# Khác với ví dụ CMD phẳng trong spec gốc (giả định auto_tts.py nằm ở repo
# root) — repo này dùng layout thật: `pipeline/` + `voxdirector/` là 2 package
# con, và `vieneu` (engine TTS) là chính package của repo này (src/ layout,
# cài qua `pip install .`), không phải 1 dependency ngoài duy nhất.
FROM python:3.11-slim

# ffmpeg: dùng bởi pipeline/audio_postprocess.py + pipeline/video_renderer.py.
# fonts-noto: font tiếng Việt cho phụ đề ghi cứng (giống notebook Colab —
# thiếu font này, phụ đề có dấu sẽ hiển thị thành ô vuông).
# build-essential + cmake: `vieneu` (cài ở bước dưới) phụ thuộc cứng vào
# llama-cpp-python==0.3.16 (dùng cho backbone GGUF — pipeline/auto_tts.py
# KHÔNG dùng nhánh đó, xem init_tts(), nhưng đây vẫn là base dependency bắt
# buộc của gói `vieneu`) — package này không có sẵn wheel dựng sẵn cho mọi
# tổ hợp platform/Python, nên pip phải tự biên dịch từ source, cần compiler.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg fonts-noto build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --retries/--timeout: build environment ở đây gặp vài lần đứt kết nối PyPI
# giữa chừng khi tải nhiều package liên tiếp — pip mặc định không retry đủ
# kiên nhẫn cho việc đó.
ENV PIP_DEFAULT_TIMEOUT=100
ENV PIP_RETRIES=10
RUN pip install --upgrade pip

# Cài package `vieneu` (engine TTS, chính là source của repo này) trước —
# tách COPY riêng để tận dụng Docker layer cache: layer install chỉ
# invalidate khi src/ hoặc pyproject.toml đổi, không phải mỗi khi sửa
# pipeline/ hay voxdirector/.
#
# QUAN TRỌNG: cài BASE package (không dùng extras "[gpu]") — "[gpu]" kéo
# theo `lmdeploy` (chỉ dùng cho mode="fast"/LMDeploy backend, KHÔNG phải
# mode="standard" mà pipeline/auto_tts.py dùng), và lmdeploy tự kéo theo 1
# cây dependency khổng lồ không liên quan (flash-linear-attention, xgrammar,
# torchvision, openai SDK, mmengine...) — từng khiến bước resolve dependency
# của pip chạy 40+ phút rồi mới lỗi vì timeout mạng giữa chừng khi build
# thử image này. torch/neucodec/transformers/accelerate (thứ THẬT SỰ cần
# cho mode="standard") đã được cài tường minh qua pipeline_requirements.txt
# ở bước dưới — không cần "[gpu]" nữa.
COPY pyproject.toml README_PYPI.md LICENSE ./
COPY src/ src/
RUN pip install --no-cache-dir .

# Dependencies riêng cho pipeline/ (VieNeu-Audio) + voxdirector/ (4 Agent:
# Alpha/Beta/Gamma/Delta) — xem pipeline_requirements.txt.
COPY pipeline_requirements.txt .
RUN pip install --no-cache-dir -r pipeline_requirements.txt

# neucodec kéo theo torchtune (dùng RotaryPositionalEmbeddings cho codec
# decoder) -> torchtune import trực tiếp torchao.dtypes.nf4tensor mà KHÔNG
# khai báo torchao là dependency chính thức của nó (kiểm tra qua PyPI JSON
# API: torchtune 0.6.1 requires_dist không hề có "torchao"). torchtune 0.6.1
# là bản phát hành CUỐI CÙNG (2025-04-07) — đã hơn 1 năm không cập nhật —
# trong khi torchao tiếp tục phát triển và ĐÃ TÁI CẤU TRÚC lại nf4tensor sau
# đó, khiến "pip install -U torchao" (kéo bản torchao MỚI NHẤT) xoá mất
# đúng path mà torchtune 0.6.1 cần → ModuleNotFoundError. Test thật trên
# Cloud Run cho thấy nâng CẢ BA package lên "mới nhất" (kể cả cùng 1 lệnh
# pip) vẫn lỗi y hệt — không phải vấn đề resolver, mà là torchao mới nhất và
# torchtune mới nhất KHÔNG tương thích với nhau, chấm hết.
#
# Fix: GHIM torchao==0.10.0 — phát hành đúng CÙNG NGÀY 2025-04-07 với
# torchtune 0.6.1 (kiểm tra qua PyPI release history), đã xác nhận còn giữ
# torchao/dtypes/nf4tensor.py (tải thử wheel về kiểm tra trực tiếp trước khi
# ghim, không đoán mò).
RUN pip install --no-cache-dir torchao==0.10.0

COPY pipeline/ pipeline/
COPY voxdirector/ voxdirector/
# assets/voxdirector_icon.png: dùng làm favicon_path cho pwa=True trong
# app.launch() (xem cuối pipeline/auto_tts.py, Section 11.7 của spec) — nếu
# không COPY riêng ở đây, container sẽ thiếu file này (Dockerfile không dùng
# "COPY . .") và PWA icon sẽ rơi về None (launch vẫn chạy được, chỉ là không
# có icon cài đặt trên bản Cloud Run phụ).
COPY assets/ assets/

# Tải sẵn model weights faster-whisper (Agent Delta) vào image lúc build —
# tránh cold-start chậm vì phải tải lại mỗi lần container khởi động (xem
# Section 11.5 của spec). Đổi "medium" nếu VOXDIRECTOR_WHISPER_MODEL khác.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('medium', device='cpu', compute_type='int8')"

# Cloud Run cấp cổng qua biến môi trường PORT lúc chạy (không cố định) —
# pipeline/auto_tts.py đọc os.environ["PORT"] khi launch(), xem cuối file đó.
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "pipeline.auto_tts"]
