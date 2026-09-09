"""Phát hiện thiết bị (CPU/GPU) dùng CHUNG cho toàn bộ dự án — 1 nguồn sự
thật duy nhất, không hardcode "cpu"/"cuda" rải rác ở nhiều nơi (VieNeu-TTS
trong pipeline/auto_tts.py, faster-whisper của Agent Delta trong
voxdirector/config.py).

Phải hoạt động đúng CẢ HAI trường hợp:
- Đường dẫn mặc định hiện tại của dự án trên máy CPU này: torch-free hoàn
  toàn (backbone GGUF qua llama-cpp-python + codec ONNX qua onnxruntime — xem
  quyết định 2026-09-08 trong pipeline_requirements.txt).
- Máy khác có cài torch (vd. nếu sau này quay lại dùng codec torch-based, hoặc
  máy demo GPU cài đặt khác đi).

GIỚI HẠN QUAN TRỌNG — đọc trước khi tin tưởng tuyệt đối vào detect_device():
- torch.cuda.is_available(): chính xác nhất, nhưng chỉ dùng được nếu torch
  được cài — đường dẫn mặc định hiện tại của pipeline KHÔNG cài torch, nên
  kênh này thường sẽ không khả dụng (không phải nghĩa là không có GPU).
- onnxruntime CUDAExecutionProvider: chỉ có ý nghĩa nếu đang cài
  "onnxruntime-gpu" — dự án hiện dùng "onnxruntime" bản CPU-only thường, nên
  kênh này sẽ luôn báo "không có CUDA" cho tới khi nào đổi sang
  onnxruntime-gpu, kể cả khi máy có GPU NVIDIA thật.
- llama-cpp-python (backbone GGUF của VieNeu-TTS): KHÔNG có API runtime nào
  để hỏi "bản đang cài có hỗ trợ GPU không" — điều đó do BẢN WHEEL đã cài
  quyết định (build có CUDA hay không), không phải 1 cờ có thể bật lúc chạy.
  standard.py._load_backbone() luôn truyền n_gpu_layers=-1 (yêu cầu offload
  tối đa) bất kể detect_device() trả về gì — nếu wheel llama-cpp-python
  không có CUDA, nó tự lặng lẽ chạy CPU dù được yêu cầu offload. Trên máy
  demo GPU thật: PHẢI cài llama-cpp-python bản có CUDA (build riêng, không
  phải bản mặc định từ PyPI) thì backbone mới thực sự chạy trên GPU — hàm
  dưới đây không thể tự kiểm tra hay đảm bảo điều đó.

Nói cách khác: detect_device() trả lời đúng câu hỏi "máy này CÓ vẻ có GPU khả
dụng qua framework đang cài không" để quyết định truyền device="cuda"/"cpu"
cho các lời gọi API — nó KHÔNG đảm bảo backbone GGUF sẽ thực sự dùng GPU đó.
"""

import logging
import shutil

logger = logging.getLogger("VoxDirector.device")

_cached_device = None  # detect 1 lần, dùng lại cho các lần gọi sau trong cùng tiến trình


def detect_device() -> str:
    """Trả về "cuda" hoặc "cpu". Có cache — chỉ thực sự kiểm tra 1 lần / tiến
    trình. In (print) + log rõ ràng kết quả và lý do, để nhìn thấy ngay trên
    console lúc khởi động (không cần đọc code) — vd. lúc demo."""
    global _cached_device
    if _cached_device is not None:
        return _cached_device

    device = "cpu"
    reason = "không phát hiện được GPU khả dụng qua torch hoặc onnxruntime — mặc định an toàn về CPU"

    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
            reason = f"torch.cuda.is_available()=True ({torch.cuda.get_device_name(0)})"
    except ImportError:
        pass

    if device == "cpu":
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            if "CUDAExecutionProvider" in providers:
                device = "cuda"
                reason = f"onnxruntime có CUDAExecutionProvider ({providers})"
        except ImportError:
            pass

    message = f"[VoxDirector] Thiết bị được chọn: {device.upper()} ({reason})"
    print(message)
    logger.info(message)

    # Chỉ để LOG cho người dùng biết thêm, KHÔNG dùng để đổi `device` — xem
    # giới hạn về llama-cpp-python ở docstring đầu file: có GPU vật lý không
    # đồng nghĩa framework đang cài (torch/onnxruntime bản CPU-only) nhìn
    # thấy nó, và ngược lại backbone GGUF dùng wheel CUDA riêng nên có thể vẫn
    # chạy GPU dù kênh kiểm tra ở trên báo "cpu".
    if device == "cpu" and shutil.which("nvidia-smi") is not None:
        note = (
            "[VoxDirector] Lưu ý: hệ thống có lệnh 'nvidia-smi' (có vẻ có GPU NVIDIA "
            "vật lý) nhưng torch/onnxruntime đang cài không nhìn thấy CUDA — nếu máy này "
            "có GPU thật sự muốn dùng, cần cài lại torch/onnxruntime-gpu (và, riêng cho "
            "backbone GGUF, llama-cpp-python) bản có hỗ trợ CUDA."
        )
        print(note)
        logger.info(note)

    _cached_device = device
    return device
