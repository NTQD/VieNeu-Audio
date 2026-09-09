"""Cấu hình dùng chung cho toàn bộ VoxDirector AI (4 Agent)."""

import os

# Ngưỡng tin cậy tối thiểu để 1 quyết định của Agent được coi là chắc chắn.
# Dưới ngưỡng này: Agent vẫn trả về giá trị tốt nhất có thể, nhưng đánh dấu
# needs_review=True (Alpha) hoặc để field liên quan = null (Gamma) — KHÔNG
# bao giờ chặn pipeline vì confidence thấp, chỉ đánh dấu để con người xem lại
# sau. Định nghĩa 1 nơi duy nhất, import ở mọi nơi cần dùng — không hardcode
# lại ở agent khác.
CONFIDENCE_THRESHOLD = 0.75

# Model Gemini dùng cho toàn bộ 4 Agent trong 1 lần chạy pipeline. KHÔNG dùng
# cơ chế auto-routing/multi-provider failover — mọi lệnh gọi trong 1 lần
# chạy phải cùng 1 model được ghim cứng, để kết quả có thể tái lập (quan
# trọng cho Agent Beta và đánh giá KPI ở Section 8 của spec).
# "gemini-2.5-flash" (giá trị cũ) trả lỗi 404 NOT_FOUND thật khi test Agent
# Alpha (2026-09-08) — API báo model này không còn cấp cho user mới, khuyến
# nghị đổi sang "gemini-3.6-flash".
GEMINI_MODEL = os.environ.get("VOXDIRECTOR_GEMINI_MODEL", "gemini-3.6-flash")

# API key đọc từ biến môi trường — KHÔNG hardcode key trong code.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

# ChromaDB: nơi lưu Character Glossary (persistent, sống sót qua các lần
# chạy khác nhau).
CHROMA_PERSIST_DIR = os.environ.get(
    "VOXDIRECTOR_CHROMA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma"),
)
GLOSSARY_COLLECTION_NAME = "character_glossary"
GLOSSARY_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GLOSSARY_TOP_K = 10

# Agent Delta (QA): kích thước model Whisper. "medium" cho lần đánh giá KPI
# cuối cùng (chính xác hơn); có thể dùng model nhỏ/nhanh hơn khi đang phát
# triển/thử nghiệm lặp lại để tiết kiệm thời gian.
WHISPER_MODEL_SIZE = os.environ.get("VOXDIRECTOR_WHISPER_MODEL", "medium")
# Mặc định: tự phát hiện qua device_utils.detect_device() (dùng chung với
# pipeline/auto_tts.py — 1 nguồn sự thật duy nhất cho CPU/GPU, không hardcode
# "cpu" ở đây nữa). VOXDIRECTOR_WHISPER_DEVICE vẫn được ưu tiên nếu người
# dùng chủ động set — cho phép ép CPU/GPU thủ công khi cần mà không cần sửa
# code.
from voxdirector.device_utils import detect_device

WHISPER_DEVICE = os.environ.get("VOXDIRECTOR_WHISPER_DEVICE") or detect_device()
WHISPER_COMPUTE_TYPE = os.environ.get("VOXDIRECTOR_WHISPER_COMPUTE_TYPE", "int8")
WER_PASS_THRESHOLD = 0.08
