import os
import sys

# Môi trường Cloud Run (deployment PHỤ, chỉ để chứng minh có thể deploy công
# khai — xem Section 11.7 của spec) tự set biến K_SERVICE trên MỌI container,
# không cần tự khai báo gì thêm; máy local (deployment CHÍNH, chạy demo thật)
# không bao giờ có biến này. Dùng để BẬT cơ chế cache model qua Google Cloud
# Storage CHỈ khi thật sự đang chạy trên Cloud Run — trên máy local, model
# tải thẳng từ Hugging Face Hub và tự cache vào đĩa cục bộ theo cơ chế mặc
# định của huggingface_hub (đĩa local KHÔNG bị xoá giữa các lần chạy như
# container Cloud Run, nên không cần tự tay quản lý cache như dưới đây).
_RUNNING_ON_CLOUD_RUN = bool(os.environ.get("K_SERVICE"))

if _RUNNING_ON_CLOUD_RUN:
    # QUAN TRỌNG: phải set TRƯỚC bất kỳ import nào có thể kéo theo
    # huggingface_hub (vd. `from vieneu import Vieneu` bên dưới) —
    # huggingface_hub đọc biến môi trường này 1 LẦN DUY NHẤT lúc chính module
    # huggingface_hub.constants được import lần đầu (gán vào hằng số
    # module-level), set trễ hơn sẽ không có tác dụng. Trỏ cache vào thư mục
    # sẽ được nạp từ Google Cloud Storage (xem _ensure_local_model bên dưới)
    # thay vì thư mục mặc định trong container — tránh phải tải lại model từ
    # Hugging Face Hub mỗi lần Cloud Run cold start (container hoàn toàn mới
    # mỗi lần scale từ 0, không giữ lại gì giữa các lần).
    os.environ.setdefault("HF_HUB_CACHE", os.path.join(
        os.environ.get("VOXDIRECTOR_MODEL_CACHE", "/tmp/voxdirector_models"), "hub",
    ))
    # Sau khi cache đã được nạp từ GCS (trong _ensure_local_model), ép mọi
    # lệnh gọi from_pretrained() chỉ đọc cache local, KHÔNG gọi mạng ra
    # Hugging Face Hub kể cả để kiểm tra bản cập nhật (mặc định vẫn gọi 1
    # HEAD request dù đã có cache) — vừa nhanh hơn, vừa không phụ thuộc
    # Hugging Face lúc runtime.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

import re
import gc
import time
import urllib.request
import gradio as gr
from concurrent.futures import ThreadPoolExecutor

# Thêm đường dẫn để import các module local và SDK
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, "src")

for p in [current_dir, project_root, src_path]:
    if p not in sys.path:
        sys.path.append(p)

from text_splitter import split_text_for_tts
from text_normalizer import normalize_text_for_tts
from vieneu import Vieneu
from voxdirector.device_utils import detect_device

# ===== GLOBAL STATE =====
tts = None
selected_voice = None
voice_list_cache = []

SAMPLE_TEXT = "rộng thêm 71,173.2 m, tức là hơn 71 km chỉ số GDP tăng 8.02%; tốc độ là 1/1000 giây. hắn tên Elyudelin. Boss cấp Trụ Thần từ level 400-499. chỉ số 10^20"
# Dùng ở Bước 2 (sau khi đã xác nhận giọng): câu dài, nhiều số/đơn vị/tên
# riêng — kiểm tra kỹ khả năng đọc của giọng đã chọn trước khi render cả
# chương. KHÔNG dùng ở Bước 1 vì quá dài, khiến việc nghe thử nhiều giọng
# liên tục để so sánh bị chậm không cần thiết.
PREVIEW_TEXT = "Xin chào, đây là giọng đọc thử để bạn tham khảo trước khi chọn."
OUTPUT_DIR = os.path.join(project_root, "outputs")
# GHI CHÚ: bản SDK vieneu đang cài KHÔNG cho phép chỉnh repetition_penalty
# qua engine.infer()/infer_batch() — backbone.generate() trong standard.py
# gọi với danh sách tham số cố định (không đọc key này từ **kwargs), nên
# không có cách nào set từ pipeline/ mà không sửa trực tiếp gói SDK bên thứ
# 3 (không nên làm, vì bản cài qua `pip install vieneu` trên Colab sẽ không
# có sửa đổi đó). Nếu lặp từ vẫn xảy ra, hướng khắc phục thực tế duy nhất
# hiện tại là báo lên tác giả VieNeu-TTS để họ mở tham số này trong SDK.
# Font phụ đề ép dùng trên Linux/Colab — nơi font "Arial" mặc định trong ASS
# không tồn tại, khiến fontconfig có thể chọn nhầm 1 font thiếu dấu tiếng
# Việt (chữ có dấu hiển thị thành ô vuông). Cần cài font này qua apt trong
# notebook Colab (vd. `apt-get install -y fonts-noto` + `fc-cache -f`).
# None trên Windows vì Arial thật đã có sẵn và hiển thị đúng dấu.
LINUX_SUBTITLE_FONT = "Noto Sans"

# Audio mẫu Ngọc Huyền — ví dụ CHÍNH THỨC có sẵn trong kho VieNeu-TTS (dùng
# để demo tính năng Voice Cloning: examples/main.py), tải trực tiếp từ repo
# gốc thay vì tự đóng gói lại, và cache 1 lần sau khi tải.
NGOC_HUYEN_URL = "https://raw.githubusercontent.com/pnnbao97/VieNeu-TTS/main/examples/audio_ref/example_ngoc_huyen.wav"
NGOC_HUYEN_CACHE = os.path.join(project_root, ".voice_cache", "ngoc_huyen.wav")
# Transcript chính xác của audio mẫu trên, lấy từ examples/main.py của kho gốc
# — encode_reference() của engine "standard" không tự nhận diện nội dung audio
# mẫu, engine BẮT BUỘC cần transcript đi kèm (xem _resolve_ref_voice trong SDK).
NGOC_HUYEN_REF_TEXT = "Tác phẩm dự thi bảo đảm tính khoa học, tính đảng, tính chiến đấu, tính định hướng."

# Backbone + codec được nạp từ Google Cloud Storage thay vì tải trực tiếp từ
# Hugging Face Hub mỗi lần container khởi động lại — trên Cloud Run, mỗi lần
# scale-to-zero rồi có traffic mới đều tạo container HOÀN TOÀN MỚI (không có
# gì được cache lại giữa các lần), nên trước đây MỖI cold start phải tải lại
# ~1.7GB từ Hugging Face qua mạng ngoài (đã quan sát thấy chậm/đôi khi treo).
# GCS cùng region với Cloud Run đi qua mạng nội bộ Google — nhanh và ổn định
# hơn nhiều.
#
# Cách làm: mirror ĐÚNG cấu trúc thư mục cache mặc định của huggingface_hub
# (`{HF_HUB_CACHE}/models--{org}--{repo}/{refs,snapshots}/...`) lên GCS, tải
# về đúng vị trí đó lúc cold start, rồi gọi Vieneu(...) với backbone_repo/
# codec_repo GIỮ NGUYÊN repo_id gốc (không đổi thành local path) — vì
# base.py._load_codec() so khớp CHUỖI CHÍNH XÁC với "neuphonic/distill-
# neucodec" để chọn class DistillNeuCodec, một local path tuỳ ý sẽ không
# khớp và bị raise ValueError. Với cache đã có sẵn đúng chỗ + HF_HUB_OFFLINE=1
# (set ở đầu file), from_pretrained() tự đọc từ local cache, không gọi mạng.
#
# Model đã được tải sẵn 1 lần (từ máy dev, có HF_TOKEN hợp lệ) và upload lên
# gs://voxdirector-ai-models/hf-cache/hub/ — không tự động hoá bước upload
# này, chỉ cần làm lại khi đổi sang bản model khác.
GCS_MODELS_BUCKET = os.environ.get("VOXDIRECTOR_MODELS_BUCKET", "voxdirector-ai-models")
GCS_HF_CACHE_PREFIX = "hf-cache/hub"
# Chỉ có giá trị thật khi _RUNNING_ON_CLOUD_RUN (xem đầu file) — trên máy
# local, biến này không được set, và _ensure_local_model() cũng không bao
# giờ được gọi (xem init_tts()), nên None ở đây vô hại.
HF_HUB_CACHE_DIR = os.environ.get("HF_HUB_CACHE")


def _ensure_local_model(hf_repo_id):
    """CHỈ dùng khi chạy trên Cloud Run (xem _RUNNING_ON_CLOUD_RUN đầu file
    và lời gọi trong init_tts() bên dưới) — trên máy local, model tải thẳng
    từ Hugging Face Hub qua from_pretrained() bình thường, dùng cache mặc
    định của huggingface_hub trên đĩa (không bị xoá giữa các lần chạy như
    container Cloud Run nên không cần tự quản lý).

    Tải model `{org}/{repo}` từ gs://{GCS_MODELS_BUCKET}/{GCS_HF_CACHE_PREFIX}/
    về đúng vị trí cache local mà huggingface_hub sẽ tự tìm tới (nếu chưa có).

    Đánh dấu ĐÃ TẢI XONG bằng 1 file marker — tránh tải lại nếu container này
    đã tải trước đó trong CÙNG vòng đời (instance được tái sử dụng cho nhiều
    request liên tiếp, không phải cold start mới)."""
    cache_folder_name = "models--" + hf_repo_id.replace("/", "--")
    local_dir = os.path.join(HF_HUB_CACHE_DIR, cache_folder_name)
    marker = os.path.join(local_dir, ".download_complete")
    if os.path.isfile(marker):
        return

    from google.cloud import storage
    client = storage.Client()
    bucket = client.bucket(GCS_MODELS_BUCKET)
    prefix = f"{GCS_HF_CACHE_PREFIX}/{cache_folder_name}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    if not blobs:
        raise RuntimeError(f"Không tìm thấy model tại gs://{GCS_MODELS_BUCKET}/{prefix}")

    for blob in blobs:
        rel_path = blob.name[len(prefix):]
        if not rel_path:
            continue
        dest_path = os.path.join(local_dir, rel_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        blob.download_to_filename(dest_path)

    with open(marker, "w") as f:
        f.write("ok")


def _load_source_text(path):
    """Đọc văn bản gốc từ file .txt hoặc .docx, luôn trả về plain text.

    .docx: chỉ trích xuất text thuần (nối các đoạn không rỗng bằng \\n) —
    KHÔNG cố giữ định dạng (bold/italic/heading style). Cấu trúc chương do
    Agent Alpha xử lý ở bước sau, không dựa vào Word heading style.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        import docx
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def init_tts():
    """Khởi tạo engine VieNeu-TTS, cache lại (chỉ tải model 1 lần).

    QUYẾT ĐỊNH (2026-09-08): dùng ĐÚNG mặc định của SDK — backbone GGUF lượng
    tử hoá (llama-cpp-python) + codec ONNX
    ("neuphonic/neucodec-onnx-decoder-int8", onnxruntime) — KHÔNG override
    codec_repo/gguf_filename như trước nữa. Đổi lại so với bản trước
    (backbone không lượng tử hoá + codec torch "neuphonic/distill-neucodec"):
    - MẤT Voice Cloning từ audio tham chiếu tự do: encode_reference() trong
      src/vieneu/base.py đòi hỏi torch vô điều kiện, và codec ONNX không có
      encode_code() — SDK hiện tại không có đường torch-free nào cho việc
      encode giọng mới. Chỉ còn dùng được các giọng có sẵn (voices.json).
    - MẤT batch thật trong infer_batch() (backbone GGUF luôn xử lý tuần tự
      từng phần một, dù gọi infer_batch() với nhiều văn bản cùng lúc) — vì
      vậy _render_chapter_audio() không còn gọi infer_batch() nữa, xem
      comment ở đó (fix lỗi audio bị cắt ngắn khi văn bản 1 phần quá dài).
    Đổi lại: chạy được HOÀN TOÀN không cần cài torch/transformers/accelerate/
    neucodec — xem pipeline_requirements.txt. Đã kiểm chứng trên máy CPU này
    (scratch_check/test_cpu_synthesis.py): RTF ~0.77, tải model ~5-9s.

    backbone_repo GIỮ NGUYÊN repo_id gốc trong mọi trường hợp. Trên Cloud Run:
    cache local đã được nạp sẵn từ GCS (xem _ensure_local_model +
    HF_HUB_CACHE/HF_HUB_OFFLINE ở đầu file) nên from_pretrained() tự đọc từ
    đó, không gọi mạng ra Hugging Face Hub. Trên máy local (đường dẫn demo
    chính — xem Section 11.7 của spec): bỏ qua bước GCS hoàn toàn,
    from_pretrained() tải thẳng từ Hugging Face Hub lần đầu rồi tự cache vào
    đĩa cục bộ theo cơ chế mặc định.

    LƯU Ý CHƯA DỌN (ngoài phạm vi phiên làm việc này — chỉ làm local, không
    đụng Cloud Run/Docker): _ensure_local_model() bên dưới vẫn đang pre-fetch
    "neuphonic/distill-neucodec" + "ntu-spml/distilhubert" cho nhánh Cloud
    Run — 2 model này giờ KHÔNG còn được dùng nữa (đã đổi codec_repo ở trên),
    nên trên Cloud Run bước này chỉ tốn thời gian/băng thông vô ích chứ không
    gây lỗi. Cần dọn lại cùng lúc với Dockerfile/GCS trong 1 phiên tập trung
    vào Cloud Run riêng.
    """
    global tts
    if tts is None:
        device = detect_device()
        if _RUNNING_ON_CLOUD_RUN:
            _ensure_local_model("pnnbao-ump/VieNeu-TTS-v2")
            _ensure_local_model("neuphonic/distill-neucodec")
            _ensure_local_model("ntu-spml/distilhubert")
        tts = Vieneu(
            emotion="storytelling",
            backbone_device=device,
        )
    return tts

def load_preset_voices():
    global voice_list_cache
    engine = init_tts()
    voice_list_cache = engine.list_preset_voices()
    choices = [f"{desc} (ID: {vid})" for desc, vid in voice_list_cache]
    if not choices:
        return gr.update(choices=["Không tìm thấy giọng nào"], value=None), "❌ Không tải được danh sách giọng."
    return gr.update(choices=choices, value=choices[0]), f"✅ Đã tải {len(choices)} giọng."

def _voice_id_from_choice(choice):
    if not choice or "(ID: " not in choice:
        return None
    return choice.split("(ID: ")[1][:-1]

def _synthesize_sample(voice_data, text):
    """Đọc `text` bằng 1 voice bất kỳ. Dùng chung cho preview nhanh ở Bước 1
    (PREVIEW_TEXT, câu ngắn) và bản mẫu kiểm tra kỹ ở Bước 2 (SAMPLE_TEXT,
    câu dài nhiều số/đơn vị/tên riêng)."""
    engine = init_tts()
    normalized = normalize_text_for_tts(text)
    audio = engine.infer(text=normalized, voice=voice_data)
    return (engine.sample_rate, audio)

def preview_voice(choice):
    """Nghe thử NGAY giọng đang chọn trong dropdown bằng 1 câu ngắn — không
    cần bấm Xác nhận và không cần sang Bước 2 — để so sánh nhiều giọng liên
    tục tại chỗ. Câu dài kiểm tra số/tên riêng dành riêng cho Bước 2, sau khi
    đã chốt giọng, để không làm chậm việc lướt qua nhiều giọng ở đây."""
    voice_id = _voice_id_from_choice(choice)
    if not voice_id:
        return None, "❌ Chưa chọn giọng để nghe thử."
    engine = init_tts()
    voice_data = engine.get_preset_voice(voice_id)
    return _synthesize_sample(voice_data, PREVIEW_TEXT), f"✅ Đang đọc thử: {choice}"

def select_preset_voice(choice):
    global selected_voice
    if not choice: return "❌ Chưa chọn giọng.", gr.update()
    engine = init_tts()
    voice_id = choice.split("(ID: ")[1][:-1]
    selected_voice = engine.get_preset_voice(voice_id)
    gr.Info(f"✅ Đã chọn: {choice}")
    return f"✅ Đã chọn: {choice}", gr.Tabs(selected=1)

def generate_sample():
    if selected_voice is None: return None, "❌ Chưa chọn giọng đọc."
    return _synthesize_sample(selected_voice, SAMPLE_TEXT), "✅ Đã tạo bản mẫu."


def fetch_ngoc_huyen_sample():
    """Tải audio mẫu Ngọc Huyền (ví dụ chính thức trong kho VieNeu-TTS) về
    máy 1 lần rồi dùng lại từ cache, để điền sẵn vào ô audio mẫu cho Voice
    Cloning bên dưới. Điền kèm luôn transcript chính xác của audio mẫu này
    (lấy từ examples/main.py của kho gốc) vì engine bắt buộc cần transcript."""
    try:
        if not os.path.isfile(NGOC_HUYEN_CACHE):
            os.makedirs(os.path.dirname(NGOC_HUYEN_CACHE), exist_ok=True)
            urllib.request.urlretrieve(NGOC_HUYEN_URL, NGOC_HUYEN_CACHE)
    except Exception as e:
        return None, None, f"❌ Lỗi tải giọng mẫu Ngọc Huyền: {e}"
    return NGOC_HUYEN_CACHE, NGOC_HUYEN_REF_TEXT, "✅ Đã tải giọng mẫu Ngọc Huyền — bấm \"Nhân bản & Nghe thử\" bên dưới."

def clone_and_preview(audio_path, ref_text):
    """Nhân bản giọng từ 1 audio mẫu 3-10 giây + transcript của audio đó, rồi
    đọc thử ngay bằng câu ngắn để kiểm tra nhanh trước khi xác nhận dùng
    giọng này.

    engine.encode_reference() chỉ mã hoá audio thành ref_codes — nó KHÔNG tự
    nhận diện nội dung audio, nên bắt buộc phải có transcript đi kèm (dùng
    trong _resolve_ref_voice của SDK để suy ra ref_phonemes). Không có
    transcript, engine.infer()/infer_batch() sẽ báo lỗi "Must provide either
    'voice' dict or both 'ref_codes' and 'ref_text'."
    """
    if not audio_path or not os.path.isfile(audio_path):
        return None, None, "❌ Chưa có audio mẫu để nhân bản."
    if not ref_text or not ref_text.strip():
        return None, None, "❌ Cần nhập transcript (nội dung chính xác) của audio mẫu."
    engine = init_tts()
    try:
        ref_codes = engine.encode_reference(audio_path)
    except ImportError:
        # Quyết định 2026-09-08: init_tts() dùng codec ONNX torch-free mặc
        # định của SDK (xem docstring init_tts()) — encode_reference() đòi
        # hỏi torch vô điều kiện nên KHÔNG còn khả dụng ở cấu hình này. Bắt
        # riêng ImportError để không lộ thông báo tiếng Anh "install torch"
        # khó hiểu ra giao diện.
        return None, None, "❌ Tính năng nhân bản giọng từ audio mẫu hiện không khả dụng trên cấu hình CPU (torch-free) đang dùng — chỉ dùng được các giọng có sẵn."
    except Exception as e:
        return None, None, f"❌ Lỗi nhân bản giọng: {e}"
    voice_data = {"codes": ref_codes, "text": ref_text.strip()}
    sample = _synthesize_sample(voice_data, PREVIEW_TEXT)
    return voice_data, sample, "✅ Đã nhân bản giọng — nghe thử ở trên, bấm \"Xác nhận\" nếu ưng ý."

def confirm_cloned_voice(cloned_voice):
    global selected_voice
    if cloned_voice is None:
        return "❌ Chưa nhân bản giọng nào để xác nhận. Bấm \"Nhân bản & Nghe thử\" trước.", gr.update()
    selected_voice = cloned_voice
    gr.Info("✅ Đã xác nhận dùng giọng nhân bản.")
    return "✅ Đã xác nhận dùng giọng nhân bản.", gr.Tabs(selected=1)


def _apply_beta(chapter_text, chapter_number):
    """Chạy Agent Beta (giữ nhất quán tên riêng/thuật ngữ qua glossary
    RAG/ChromaDB) trên 1 chương ĐÃ được Agent Alpha tách sẵn, TRƯỚC khi
    normalize_text_for_tts() — đúng theo thứ tự Alpha -> Beta -> normalizer
    hiện có (xem voxdirector/agents/beta_consistency.py).

    Nếu chưa cấu hình GEMINI_API_KEY hoặc lệnh gọi Gemini lỗi: BỎ QUA Beta
    và dùng nguyên text của Alpha — Beta là bước NÂNG CAO tuỳ chọn (cần API
    key trả phí/free-tier bên ngoài), không được phép chặn pipeline chính
    nếu chưa cấu hình hoặc tạm thời lỗi mạng/API.

    Trả về (corrected_text, log_note, new_entry_candidates) — candidates là
    list[dict] (mỗi dict tự mang thêm "chapter_number") CHƯA được ghi vào
    glossary, để UI (panel "📖 Duyệt Glossary") gom lại cho người dùng xác
    nhận sau — xem process_batch() và approve_glossary_candidates().
    """
    from voxdirector.config import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        return chapter_text, "⏭️ Agent Beta: bỏ qua (chưa cấu hình GEMINI_API_KEY).\n", []
    try:
        from voxdirector.agents.beta_consistency import run_beta
        result = run_beta(chapter_text, chapter_number=chapter_number)
        candidates = result.get("new_entry_candidates", [])
        for c in candidates:
            c["chapter_number"] = chapter_number
        n_applied = len(result.get("applied_terms", []))
        note = (
            f"🔤 Agent Beta: áp dụng {n_applied} thuật ngữ đã biết từ glossary, "
            f"phát hiện {len(candidates)} thuật ngữ mới (chưa tự thêm vào glossary, cần xác nhận — xem panel Duyệt Glossary).\n"
        )
        return result["corrected_text"], note, candidates
    except Exception as e:
        return chapter_text, f"⚠️ Agent Beta lỗi ({e}) — dùng nguyên text gốc từ Agent Alpha, bỏ qua bước này.\n", []


def _apply_delta(chapter_dir, prefix, chunks):
    """Chạy Agent Delta (QA đối chiếu ASR round-trip, faster-whisper + jiwer)
    SAU KHI audio của chương đã ghép xong — ghi {prefix}_qa_report.json vào
    chapter_dir để người dùng xem lại (xem voxdirector/agents/delta_qa.py).

    THỬ NGHIỆM (theo yêu cầu người dùng, 2026-09-09): chỉ chạy khi tuỳ chọn
    "Chạy Agent Delta" ở tab Batch được bật (mặc định TẮT) — xem run_delta ở
    _process_chapter_e2e()/process_batch(). WER của faster-whisper là 1 phép
    đo GIÁN TIẾP (lỗi có thể đến từ chính ASR nhận dạng sai giọng đọc tiếng
    Việt, không hẳn từ audio TTS thật sự có vấn đề) — không thay thế cho việc
    tự nghe kiểm tra, chỉ là 1 tín hiệu tham khảo thêm.

    faster-whisper/jiwer là dependency MỚI (xem pipeline_requirements.txt),
    chưa chắc đã cài — nếu thiếu, BỎ QUA Delta hoàn toàn thay vì lỗi cả
    chương vừa render xong.

    Trả về log_note.
    """
    try:
        from voxdirector.agents.delta_qa import summarize_qa_report, verify_chapter_quality
    except ImportError as e:
        return f"⏭️ Agent Delta: bỏ qua (chưa cài faster-whisper/jiwer — {e}).\n"
    try:
        qa_report = verify_chapter_quality(chapter_dir, prefix, chunks)
        import json
        qa_path = os.path.join(chapter_dir, f"{prefix}_qa_report.json")
        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(qa_report, f, ensure_ascii=False, indent=2)
        summary = summarize_qa_report(qa_report)
        return f"🩺 Agent Delta: {summary}\n"
    except Exception as e:
        return f"⚠️ Agent Delta lỗi ({e}) — bỏ qua bước QA cho chương này.\n"


def _extract_chapter_label(chapter_text):
    """Tìm nhãn "Chương N"/"Chapter N" NGAY TRONG 1 chương ĐÃ được Agent
    Alpha phân tách sẵn — chỉ để đặt tên thư mục cho dễ nhận biết, KHÔNG
    dùng để tách chương (Alpha đảm nhiệm việc đó hoàn toàn, xem
    voxdirector/agents/alpha_ingestion.py). Chỉ quét ~200 ký tự đầu vì
    heading (nếu có) luôn nằm ở đầu chương."""
    m = re.search(r'[Cc]h(?:ương|apter)\s*(\d+)', chapter_text[:200])
    return m.group(1) if m else None

def _chapter_dir_for(chapter_text, source_path=None, chapter_idx=0, total_in_file=1):
    """Suy ra (prefix, chapter_dir, label) cho 1 chương ĐÃ được Agent Alpha
    phân tách sẵn từ raw_text của 1 file upload.

    Khi KHÔNG tìm thấy "Chương N" / "Chapter N" trong text (label = None),
    KHÔNG dùng chung 1 thư mục "part" tĩnh cho mọi chương không tiêu đề —
    làm vậy thì 2 chương khác nhau sẽ bị ghi đè/trộn lẫn vào cùng thư mục, và
    với cơ chế resume (bỏ qua file .wav đã có) thì chương thứ 2 còn có thể bị
    coi nhầm là "đã render xong" bằng nội dung của chương thứ 1. Thay vào đó,
    dùng tên file nguồn + số thứ tự chương trong file đó làm phần phân biệt.
    """
    label = _extract_chapter_label(chapter_text)
    if label:
        prefix = f"C_{label}"
    else:
        base = os.path.splitext(os.path.basename(source_path))[0] if source_path else "unknown"
        base = re.sub(r'[^\w\-]+', '_', base).strip('_') or "unknown"
        prefix = f"part_{base}" if total_in_file <= 1 else f"part_{base}_{chapter_idx + 1}"
    return prefix, os.path.join(OUTPUT_DIR, prefix), label

def _is_chapter_complete(chapter_dir, prefix, want_video):
    """Chương coi là XONG nếu: có ảnh nền -> đã có video; không có ảnh nền ->
    đã có audio ghép + phụ đề. Dùng để BỎ QUA hẳn 1 chương khi chạy batch,
    tránh làm lại từ đầu những chương đã xử lý xong ở lần chạy trước."""
    if want_video:
        p = os.path.join(chapter_dir, f"{prefix}_video.mp4")
    else:
        p = os.path.join(chapter_dir, f"{prefix}_merged.srt")
    return os.path.isfile(p) and os.path.getsize(p) > 0

def _render_chapter_audio(chapter_text_norm, prefix, chapter_dir, progress_cb=None):
    """Bước 3: chia phần -> render audio (batch GPU, có resume).

    chapter_text_norm: text của ĐÚNG 1 chương — đã được Agent Alpha phân
    tách khỏi raw_text của file upload (xem _process_chapter_e2e) và đã
    normalize_text_for_tts(). Hàm này KHÔNG còn tự tách chương/normalize gì
    thêm — trước đây có 1 vòng tách "Chương N" bằng regex ngay trong hàm
    này, giờ đã bỏ hẳn vì Agent Alpha đã tách chương từ sớm hơn, ở mức toàn
    bộ raw_text của file, chính xác hơn (xử lý được cả văn bản không có
    heading tường minh).

    progress_cb(done, total, desc), nếu có, được gọi sau mỗi lô render.
    Trả về (log, generated_files, total_chunks).
    """
    if selected_voice is None:
        raise RuntimeError("Chưa chọn giọng. Quay lại Bước 1.")
    if not chapter_text_norm.strip():
        raise RuntimeError("Chương trống.")

    engine = init_tts()
    os.makedirs(chapter_dir, exist_ok=True)

    # Lưu text gốc vào thư mục chương để subtitle_generator dùng
    text_save_path = os.path.join(chapter_dir, f"{prefix}.txt")
    with open(text_save_path, "w", encoding="utf-8") as tf:
        tf.write(chapter_text_norm)

    # Liệt kê TOÀN BỘ các phần cần có trước, kèm đường dẫn file đích. Không
    # còn 2 cấp "chương trong file / phần trong chương" như trước — mỗi thư
    # mục giờ LUÔN LÀ đúng 1 chương (Agent Alpha đảm bảo điều này), nên chỉ
    # còn 1 cấp "phần trong chương".
    all_parts = []
    for p_idx, chunk in enumerate(split_text_for_tts(chapter_text_norm, 250)):
        filename = f"{prefix}_p{p_idx+1:02d}.wav"
        output_file = os.path.abspath(os.path.join(chapter_dir, filename))
        all_parts.append({"filename": filename, "path": output_file, "text": chunk, "words": len(chunk.split())})

    total_chunks = len(all_parts)

    # Bỏ qua phần đã render sẵn (file .wav tồn tại và không rỗng) — quan trọng
    # khi chạy trên Colab vì phiên có thể ngắt kết nối giữa chừng; không có
    # bước này thì phải render lại từ đầu toàn bộ chương.
    already_done = [p for p in all_parts if os.path.isfile(p["path"]) and os.path.getsize(p["path"]) > 0]
    pending = [p for p in all_parts if p not in already_done]

    log = f"📖 Chương {prefix} — {total_chunks} phần"
    log += f" ({len(already_done)} đã render sẵn, bỏ qua)\n" if already_done else "\n"

    done_count = len(already_done)
    t_render_start = time.time()
    # QUAN TRỌNG (2026-09-09, fix lỗi audio "vô nghĩa"/bị cắt ngắn trong
    # Batch): TRƯỚC ĐÂY gọi thẳng engine.infer_batch() với nguyên văn bản
    # từng phần (tới 250 TỪ, tức có thể 1000-1200+ KÝ TỰ) trong 1 lần gọi
    # _infer_ggml() duy nhất — nhưng infer()/infer_batch() của SDK (xem
    # src/vieneu/standard.py) tự chia nhỏ văn bản theo max_chars=256 KÝ TỰ
    # (qua split_text_into_chunks(), hoàn toàn khác _cấp_ với 250 TỪ ở đây)
    # rồi mới đưa từng mảnh nhỏ qua model — infer_batch() gọi TRỰC TIẾP thì
    # KHÔNG đi qua bước tự chia nhỏ an toàn này. Hệ quả: prompt quá dài so
    # với ngân sách sinh token của 1 lần gọi backbone GGUF (n_ctx giới hạn),
    # khiến model bị cắt ngang giữa chừng — audio ra nghe cụt/rối loạn dù
    # không có lỗi nào được raise. Đã xác nhận THẬT bằng cách đo tốc độ
    # từ/giây thực tế: ~250 từ/phần cho ra ~8-11 từ/giây (không thể là giọng
    # nói thật, tốc độ tự nhiên ~3-5 từ/giây) khi gọi infer_batch() thẳng,
    # nhưng ĐÚNG tốc độ khi gọi qua engine.infer() (tự chia theo max_chars).
    #
    # Fix: gọi engine.infer() cho TỪNG phần (KHÔNG dùng infer_batch() thẳng
    # nữa) — infer() tự lo việc chia nhỏ an toàn + ghép lại liền mạch, nên
    # 1 file .wav vẫn tương ứng ĐÚNG 1 "phần" 250-từ như trước (không đổi
    # cấu trúc file mà subtitle_generator.py/Delta đang phụ thuộc vào), chỉ
    # có khâu sinh audô BÊN TRONG mỗi phần là an toàn hơn. Với backbone GGUF
    # (xem init_tts()), infer_batch() vốn dĩ cũng đã xử lý tuần tự từng mục
    # một (không batch thật — xem comment trong standard.py), nên gọi
    # infer() tuần tự ở đây không làm chậm thêm so với trước.
    for part in pending:
        if progress_cb:
            progress_cb(done_count, total_chunks, f"render {part['filename']} ({part['words']} từ)")
        audio = engine.infer(part["text"], voice=selected_voice)
        engine.save(audio, part["path"])
        log += f"✅ {part['filename']} ({part['words']} từ)\n"
        done_count += 1
    render_elapsed = time.time() - t_render_start

    gc.collect()
    generated_files = [p["path"] for p in all_parts]
    log += f"🎉 Audio xong: {total_chunks} file .wav\n"
    log += f"⏱️ Render audio: {render_elapsed:.1f}s ({len(pending)} phần mới)\n"
    return log, generated_files, total_chunks

def _run_postprocess_core(chapter_dir, prefix, chapter_text_norm, bgm_path, bgm_volume, silence_dur, bg_image_path, font_size,
                           progress_cb=None, burn_subtitles=True):
    """Bước 4: ghép audio -> trộn BGM (nếu có) -> tạo phụ đề -> render video (nếu có ảnh nền).

    chapter_dir/prefix: do caller (_process_chapter_e2e) truyền vào — không
    tự suy lại từ file path nữa (trước đây đọc lại text_file_path và tự gọi
    _chapter_dir_for lần 2, dư thừa so với lần gọi ở Bước 3 và có thể lệch
    nếu logic tách chương thay đổi giữa 2 lần gọi).

    progress_cb(fraction 0..1, desc), nếu có, được gọi ở mỗi giai đoạn.
    burn_subtitles=False: bỏ qua bước ghi cứng phụ đề (nhanh hơn nhiều) —
    vẫn tạo ra video (ảnh nền + audio) và file .srt riêng để tự upload lên
    YouTube làm phụ đề (Video > Phụ đề) thay vì ghi cứng vào hình.
    Trả về (log, video_path_or_None).
    """
    from audio_postprocess import get_ffmpeg, get_wav_files, concat_with_silence, mix_bgm
    from subtitle_generator import generate_srt
    from video_renderer import render_video

    if not os.path.isdir(chapter_dir):
        raise RuntimeError(f"Thư mục chương không tồn tại: {chapter_dir}. Chưa render audio.")

    log = ""
    ffmpeg = get_ffmpeg()  # ném FileNotFoundError nếu chưa cài — để caller xử lý
    log += f"🛠️ FFmpeg: {ffmpeg}\n"

    wav_files = get_wav_files(chapter_dir)
    if not wav_files:
        raise RuntimeError(f"Không tìm thấy file .wav trong {chapter_dir}.")

    if progress_cb: progress_cb(0.1, "đang ghép audio")
    log += "[1/3] GHÉP AUDIO\n"
    t0 = time.time()
    merged_wav = os.path.join(chapter_dir, f"{prefix}_merged.wav")
    concat_with_silence(ffmpeg, wav_files, silence_dur, merged_wav)
    log += f"✅ Ghép {len(wav_files)} file, silence={silence_dur}s — ⏱️ {time.time() - t0:.1f}s\n"

    final_audio = merged_wav
    if bgm_path and os.path.isfile(bgm_path):
        if progress_cb: progress_cb(0.25, "đang trộn nhạc nền")
        log += f"\n🎵 TRỘN BGM (volume: {bgm_volume})\n"
        t0 = time.time()
        bgm_wav = os.path.join(chapter_dir, f"{prefix}_final.wav")
        mix_bgm(ffmpeg, merged_wav, bgm_path, bgm_wav, bgm_volume)
        final_audio = bgm_wav
        log += f"✅ Đã trộn nhạc nền — ⏱️ {time.time() - t0:.1f}s\n"

    if progress_cb: progress_cb(0.4, "đang tạo phụ đề")
    log += "\n[2/3] TẠO PHỤ ĐỀ (từ text gốc)\n"
    t0 = time.time()
    text_save_path = os.path.join(chapter_dir, f"{prefix}.txt")
    if not os.path.isfile(text_save_path):
        with open(text_save_path, "w", encoding="utf-8") as tf:
            tf.write(chapter_text_norm)
    srt_path = generate_srt(chapter_dir, text_save_path, silence_dur, max_chars=60)
    if not srt_path:
        raise RuntimeError("Lỗi tạo phụ đề.")
    log += f"✅ Đã tạo: {os.path.basename(srt_path)} — ⏱️ {time.time() - t0:.1f}s\n"

    if not bg_image_path:
        log += "\n⚠️ Chưa có ảnh nền → dừng ở bước audio + subtitle (không tạo video).\n"
        if progress_cb: progress_cb(1.0, "xong (chưa có video)")
        return log, None

    if progress_cb: progress_cb(0.5, "đang render video (tự dò encoder)")
    log += "\n[3/3] RENDER VIDEO" + (" (không ghi cứng phụ đề)" if not burn_subtitles else "") + "\n"
    t0 = time.time()
    out_mp4 = os.path.join(chapter_dir, f"{prefix}_video.mp4")
    font_name = None if sys.platform == "win32" else LINUX_SUBTITLE_FONT
    used_encoder = render_video(
        final_audio, bg_image_path, srt_path, out_mp4, font_size=font_size,
        font_name=font_name, burn_subtitles=burn_subtitles,
    )
    video_elapsed = time.time() - t0

    if not os.path.isfile(out_mp4):
        raise RuntimeError("Lỗi render video. Kiểm tra log FFmpeg.")
    size_mb = os.path.getsize(out_mp4) / (1024 * 1024)
    log += f"✅ Video: {os.path.basename(out_mp4)} ({size_mb:.1f} MB) — encoder: {used_encoder}\n"
    log += f"⏱️ Render video{'' if burn_subtitles else ' (không ghi cứng phụ đề)'}: {video_elapsed:.1f}s\n"
    if progress_cb: progress_cb(1.0, "hoàn tất")
    return log, out_mp4

def _process_chapter_e2e(text_file_path, bgm_path, bgm_volume, silence_dur, bg_image_path, font_size,
                          render_cb=None, pp_cb=None, burn_subtitles=True, run_delta=False):
    """Chạy trọn 1 FILE upload: Agent Alpha phân tách raw_text thành N chương
    (thay thế hoàn toàn 2 chỗ tách chương bằng regex hardcode trước đây) —
    rồi với MỖI chương: Bước 3 (render audio) nối liền Bước 4 (hậu kỳ +
    video), không cần thao tác tay giữa 2 bước. Tự bỏ qua chương nào đã xong
    từ trước.

    Trả về (results, glossary_candidates):
    - results: list[dict] — 1 phần tử / chương, mỗi phần tử có key: prefix,
      log, video_path (hoặc None), skipped (bool), needs_review (bool — Agent
      Alpha không chắc chắn về ranh giới chương này, xem confidence_score
      trong log).
    - glossary_candidates: list[dict] gộp từ new_entry_candidates của Agent
      Beta qua MỌI chương trong file này (chưa ghi vào glossary — chờ người
      dùng duyệt qua panel "📖 Duyệt Glossary").
    """
    from voxdirector.agents.alpha_ingestion import segment_chapters

    raw_text = _load_source_text(text_file_path)
    alpha_chapters = segment_chapters(raw_text)
    want_video = bool(bg_image_path)
    results = []
    glossary_candidates = []

    for c_idx, chap in enumerate(alpha_chapters):
        n_chapters = len(alpha_chapters)
        # Suy prefix/chapter_dir từ text GỐC của Alpha (chưa qua Beta/normalize)
        # để kiểm tra resume-skip TRƯỚC KHI gọi Agent Beta — Beta gọi Gemini
        # API bên ngoài (có thể tốn phí), không nên gọi cho chương đã render
        # xong từ trước. Heading "Chương N" (nếu có) không đổi qua Beta nên
        # dùng label từ text gốc là đủ, không cần tính lại sau khi có
        # corrected_text.
        prefix, chapter_dir, label = _chapter_dir_for(
            chap["text"], source_path=text_file_path,
            chapter_idx=c_idx, total_in_file=n_chapters,
        )

        if _is_chapter_complete(chapter_dir, prefix, want_video):
            existing = os.path.join(chapter_dir, f"{prefix}_video.mp4") if want_video else None
            results.append({
                "prefix": prefix, "log": f"⏭️ {prefix}: đã xử lý xong từ trước, bỏ qua.\n",
                "video_path": existing, "skipped": True, "needs_review": chap["needs_review"],
            })
            continue

        corrected_text, beta_note, beta_candidates = _apply_beta(chap["text"], chapter_number=c_idx + 1)
        glossary_candidates.extend(beta_candidates)
        text_norm = normalize_text_for_tts(corrected_text)

        def _render_cb(done, total, desc, _c_idx=c_idx, _n=n_chapters):
            if render_cb:
                render_cb(done, total, f"[chương {_c_idx + 1}/{_n}] {desc}")

        def _pp_cb(frac, desc, _c_idx=c_idx, _n=n_chapters):
            if pp_cb:
                pp_cb(frac, f"[chương {_c_idx + 1}/{_n}] {desc}")

        t_total = time.time()
        render_log, _, _ = _render_chapter_audio(text_norm, prefix, chapter_dir, progress_cb=_render_cb)
        pp_log, video_path = _run_postprocess_core(
            chapter_dir, prefix, text_norm, bgm_path, bgm_volume, silence_dur, bg_image_path, font_size,
            progress_cb=_pp_cb, burn_subtitles=burn_subtitles,
        )
        if run_delta:
            delta_note = _apply_delta(chapter_dir, prefix, split_text_for_tts(text_norm, 250))
        else:
            delta_note = "⏭️ Agent Delta: bỏ qua (tính năng THỬ NGHIỆM, chưa bật ở tuỳ chọn Batch — tự nghe/kiểm tra thủ công như bình thường).\n"
        total_elapsed = time.time() - t_total
        log = beta_note + render_log + "\n" + pp_log + "\n" + delta_note + f"\n⏱️ TỔNG THỜI GIAN CHƯƠNG: {total_elapsed:.1f}s\n"
        if not label:
            log += (
                f"⚠️ Agent Alpha không tìm thấy \"Chương N\"/\"Chapter N\" tường minh trong chương "
                f"này — dùng tên file + số thứ tự làm thư mục ({prefix}).\n"
            )
        if chap["needs_review"]:
            log += (
                f"⚠️ Agent Alpha KHÔNG chắc chắn về ranh giới chương này "
                f"(confidence={chap['confidence_score']:.2f} < ngưỡng) — nên xem lại thủ công.\n"
            )

        results.append({
            "prefix": prefix, "log": log, "video_path": video_path,
            "skipped": False, "needs_review": chap["needs_review"],
        })

    return results, glossary_candidates

def scan_output_health():
    """Quét toàn bộ outputs/ và báo cáo chương nào đang THIẾU file — để phát
    hiện NGAY những chương dở dang (như sự cố chương 1990 trước đây: có audio
    nhưng thiếu hẳn phụ đề/video vì hậu kỳ bị gián đoạn giữa chừng), thay vì
    tình cờ phát hiện ra sau này. "Chưa có video" một mình KHÔNG bị tính là
    lỗi (có thể do cố ý không dùng ảnh nền) — chỉ thiếu audio/phụ đề/text gốc
    mới được coi là vấn đề thật sự.
    """
    if not os.path.isdir(OUTPUT_DIR):
        return "⚠️ Chưa có thư mục outputs/ — chưa render chương nào."

    rows = []
    for name in sorted(os.listdir(OUTPUT_DIR)):
        chapter_dir = os.path.join(OUTPUT_DIR, name)
        if not os.path.isdir(chapter_dir):
            continue
        files = os.listdir(chapter_dir)
        parts = [f for f in files if re.match(rf"^{re.escape(name)}_p\d+\.wav$", f)]
        has_txt = f"{name}.txt" in files
        has_merged = f"{name}_merged.wav" in files
        srt_path = os.path.join(chapter_dir, f"{name}_merged.srt")
        has_srt = os.path.isfile(srt_path) and os.path.getsize(srt_path) > 0
        video_path = os.path.join(chapter_dir, f"{name}_video.mp4")
        has_video = os.path.isfile(video_path) and os.path.getsize(video_path) > 0

        issues = []
        if not parts:
            issues.append("không có file audio nào")
        if parts and not has_merged:
            issues.append("chưa ghép audio (thiếu _merged.wav)")
        if parts and not has_srt:
            issues.append("thiếu phụ đề .srt — hậu kỳ có thể đã bị gián đoạn")
        if not has_txt:
            issues.append("thiếu text gốc .txt — không thể tạo lại phụ đề nếu cần")

        rows.append((name, len(parts), has_video, issues))

    if not rows:
        return "⚠️ outputs/ chưa có chương nào."

    bad = [r for r in rows if r[3]]
    report = f"🩺 KIỂM TRA {len(rows)} CHƯƠNG trong outputs/\n"
    report += f"✅ {len(rows) - len(bad)} chương ổn (đủ audio + phụ đề)\n"
    if bad:
        report += f"⚠️ {len(bad)} chương CÓ VẤN ĐỀ:\n"
        for name, n_parts, has_video, issues in bad:
            report += f"  • {name} ({n_parts} phần audio, {'có' if has_video else 'chưa có'} video): {', '.join(issues)}\n"
    else:
        report += "🎉 Không có chương nào thiếu file!\n"
    return report

def process_batch(input_files, bgm_file, bgm_volume, silence_dur, bg_image, font_size, burn_subtitles,
                   run_delta=False, progress=gr.Progress(track_tqdm=False)):
    """Handler cho nút Batch: nhận nhiều file .txt/.docx, mỗi file được Agent
    Alpha tự phân tách thành N chương, rồi chạy Bước 3 -> Bước 4 liên tục cho
    từng chương, tự bỏ qua chương đã xong, và KHÔNG dừng cả batch nếu 1 file
    bị lỗi — để có thể để máy chạy qua đêm không cần trông chừng.

    run_delta: mặc định TẮT — Agent Delta (QA đối chiếu ASR) là tính năng
    THỬ NGHIỆM, chỉ chạy khi người dùng chủ động bật ở checkbox tương ứng
    (xem UI bên dưới)."""
    if selected_voice is None:
        return "❌ Chưa chọn giọng. Quay lại Bước 1.", [], []
    if not input_files:
        return "❌ Chưa chọn file nào.", [], []

    bgm_path = bgm_file.name if (bgm_file and hasattr(bgm_file, 'name')) else bgm_file
    img_path = bg_image.name if (bg_image and hasattr(bg_image, 'name')) else bg_image

    # Sắp xếp theo tên file để thứ tự chạy dễ đoán (vd. chương thấp -> cao).
    file_paths = sorted(f.name for f in input_files)
    total_files = len(file_paths)

    full_log = f"🌙 BATCH: {total_files} file — Agent Alpha tự phân tách chương trong từng file, chương đã xong sẽ tự động được bỏ qua.\n\n"
    videos, n_done, n_skipped, n_failed, n_needs_review = [], 0, 0, 0, 0
    all_candidates = []
    t_batch = time.time()

    for idx, fp in enumerate(file_paths):
        label = os.path.basename(fp)

        def render_cb(done, total, desc, _idx=idx, _label=label):
            local = (done / total) if total else 0
            progress((_idx + local * 0.5) / total_files, desc=f"[{_idx+1}/{total_files}] {_label}: {desc}")

        def pp_cb(frac, desc, _idx=idx, _label=label):
            progress((_idx + 0.5 + frac * 0.5) / total_files, desc=f"[{_idx+1}/{total_files}] {_label}: {desc}")

        progress(idx / total_files, desc=f"[{idx+1}/{total_files}] Bắt đầu {label} (Agent Alpha đang phân tách chương)...")
        try:
            chapter_results, file_candidates = _process_chapter_e2e(
                fp, bgm_path, bgm_volume, silence_dur, img_path, font_size,
                render_cb=render_cb, pp_cb=pp_cb, burn_subtitles=burn_subtitles, run_delta=run_delta,
            )
            all_candidates.extend(file_candidates)
            full_log += f"=== {label} — Agent Alpha tách thành {len(chapter_results)} chương ===\n"
            for r in chapter_results:
                full_log += f"--- {r['prefix']} ---\n{r['log']}\n"
                n_skipped += int(r["skipped"])
                n_done += int(not r["skipped"])
                n_needs_review += int(r["needs_review"])
                if r["video_path"]:
                    videos.append(r["video_path"])
        except FileNotFoundError:
            n_failed += 1
            full_log += f"=== ❌ {label}: FFmpeg chưa cài. Chạy: winget install Gyan.FFmpeg rồi khởi động lại. ===\n\n"
        except Exception as e:
            n_failed += 1
            full_log += f"=== ❌ {label}: LỖI — {e} ===\n\n"

    batch_elapsed = time.time() - t_batch
    progress(1.0, desc="Hoàn tất batch!")
    full_log += f"\n🎉 BATCH XONG: {n_done} chương mới, {n_skipped} bỏ qua (đã có sẵn), {n_failed} file lỗi / tổng {total_files} file."
    full_log += f"\n⏱️ TỔNG THỜI GIAN BATCH: {batch_elapsed / 60:.1f} phút"
    if n_needs_review:
        full_log += f"\n⚠️ {n_needs_review} chương Agent Alpha đánh dấu cần xem lại ranh giới (confidence thấp) — xem chi tiết ở trên."
    if all_candidates:
        full_log += f"\n📖 Agent Beta đề xuất {len(all_candidates)} thuật ngữ mới — xem panel \"Duyệt Glossary\" bên dưới để xác nhận trước khi dùng cho các chương sau."
    full_log += "\n\n" + scan_output_health()
    return full_log, videos, _dedupe_glossary_candidates(all_candidates)


def _dedupe_glossary_candidates(candidates: list[dict]) -> list[list]:
    """Gộp new_entry_candidates từ nhiều chương/file trong 1 lần Batch —
    cùng 1 term có thể được nhiều chương cùng đề xuất (vd. nhân vật xuất
    hiện xuyên suốt); chỉ giữ lại bản có confidence_score cao nhất, nhưng
    vẫn nhớ chương PHÁT HIỆN ĐẦU TIÊN (chapter_number nhỏ nhất trong số các
    lần đề xuất) để ghi first_seen_chapter cho đúng khi duyệt.

    Trả về list các row (list, KHÔNG phải dict) đúng thứ tự cột của
    gr.Dataframe: [term, entity_type, canonical_form, confidence_score,
    chapter_number] — Term/Entity Type/Canonical Form có thể sửa trực tiếp
    trên bảng trước khi bấm Duyệt.
    """
    best_by_term: dict[str, dict] = {}
    for c in candidates:
        term = c.get("term")
        if not term:
            continue
        existing = best_by_term.get(term)
        if existing is None or c.get("confidence_score", 0) > existing.get("confidence_score", 0):
            merged = dict(c)
            if existing is not None:
                merged["chapter_number"] = min(
                    c.get("chapter_number", 0), existing.get("chapter_number", 0),
                )
            best_by_term[term] = merged
        elif existing is not None:
            existing["chapter_number"] = min(
                existing.get("chapter_number", 0), c.get("chapter_number", 0),
            )

    return [
        [c["term"], c.get("entity_type", "term"), c.get("canonical_form", c["term"]),
         round(c.get("confidence_score", 0.0), 2), c.get("chapter_number", 0)]
        for c in sorted(best_by_term.values(), key=lambda c: -c.get("confidence_score", 0))
    ]


def approve_glossary_candidates(table_rows):
    """Handler cho nút '✅ Duyệt & Lưu vào Glossary' — đọc đúng nội dung
    HIỆN TẠI trên bảng (người dùng có thể đã sửa Canonical Form/Entity Type,
    hoặc xoá bớt dòng không muốn duyệt trước khi bấm — Gradio Dataframe cho
    xoá dòng qua UI có sẵn), rồi ghi vào ChromaDB qua approve_new_entries().
    KHÔNG tự động chạy — chỉ chạy khi người dùng chủ động bấm nút, đúng
    nguyên tắc "chờ xác nhận từ con người" của Agent Beta."""
    if table_rows is None or len(table_rows) == 0:
        return "❌ Không có thuật ngữ nào trên bảng để duyệt.", []

    from voxdirector.agents.beta_consistency import approve_new_entries

    candidates = []
    for row in table_rows:
        term, entity_type, canonical_form, confidence_score, chapter_number = (list(row) + [None] * 5)[:5]
        if not term:
            continue
        candidates.append({
            "term": term, "entity_type": entity_type,
            "canonical_form": canonical_form or term,
            "confidence_score": confidence_score,
            "chapter_number": int(chapter_number) if chapter_number else 0,
        })

    valid_types = {"character", "place", "term"}
    n_valid = sum(1 for c in candidates if c["entity_type"] in valid_types)
    n_skipped = len(candidates) - n_valid
    try:
        approve_new_entries(candidates)
    except Exception as e:
        return f"❌ Lỗi khi ghi vào glossary: {e}", table_rows

    msg = f"✅ Đã lưu {n_valid} thuật ngữ vào glossary."
    if n_skipped:
        msg += f" ⚠️ Bỏ qua {n_skipped} dòng có entity_type không hợp lệ (phải là character/place/term)."
    return msg, []

# ===== GIAO DIỆN GRADIO =====
with gr.Blocks(title="VieNeu-TTS Auto Reader", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🦜 VieNeu-TTS — Sản xuất Audiobook tự động")
    gr.Markdown("**Quy trình khép kín:** Chọn giọng → Nghe mẫu → Batch: Audio → Video (chạy liên tục, tự bỏ qua chương đã xong)")

    with gr.Tabs() as tabs:
        # ========== BƯỚC 1 ==========
        with gr.Tab("① Chọn giọng", id=0):
            gr.Markdown("### Chọn giọng đọc từ danh sách preset")
            btn_load = gr.Button("📂 Tải danh sách giọng", variant="secondary")
            preset_dropdown = gr.Dropdown(label="Chọn giọng preset", choices=[], interactive=True)
            load_status = gr.Textbox(label="Trạng thái tải", interactive=False)

            gr.Markdown("*Nghe thử nhanh giọng đang chọn ở trên bằng 1 câu ngắn — đổi giọng và bấm lại thoải mái để so sánh, không cần Xác nhận trước. Muốn kiểm tra kỹ khả năng đọc số/tên riêng, dùng \"Tạo bản mẫu\" ở Bước 2 sau khi đã xác nhận.*")
            btn_preview = gr.Button("🔊 Nghe thử giọng này", variant="secondary")
            preview_audio = gr.Audio(label="Bản đọc thử", elem_id="voice1_preview_player")
            preview_status = gr.Textbox(label="Trạng thái nghe thử", interactive=False)

            btn_select_preset = gr.Button("✅ Xác nhận giọng", variant="primary")
            voice_status = gr.Textbox(label="Trạng thái chọn giọng", interactive=False)

            btn_load.click(fn=load_preset_voices, outputs=[preset_dropdown, load_status])
            btn_preview.click(fn=preview_voice, inputs=preset_dropdown, outputs=[preview_audio, preview_status])
            btn_select_preset.click(fn=select_preset_voice, inputs=preset_dropdown, outputs=[voice_status, tabs])

            gr.Markdown("---")
            with gr.Accordion("🦜 Hoặc: Nhân bản giọng từ audio mẫu (Voice Cloning)", open=False):
                gr.Markdown(
                    "Tải lên 3-10 giây audio mẫu của giọng bạn muốn dùng, kèm **transcript** "
                    "(nội dung chính xác audio đang đọc) — engine cần transcript để nhân bản "
                    "đúng, không chỉ từ audio đơn thuần. Bạn cần có quyền sử dụng audio mẫu "
                    "này (giọng của chính bạn, người đồng ý cho dùng, hoặc tài nguyên được "
                    "cấp phép rõ ràng)."
                )
                clone_audio = gr.Audio(label="Audio mẫu (3-10 giây)", type="filepath")
                clone_ref_text = gr.Textbox(
                    label="Transcript audio mẫu (nội dung chính xác audio đang đọc)",
                    placeholder="Nhập đúng nội dung văn bản mà audio mẫu đang đọc...",
                    lines=2,
                )
                btn_ngoc_huyen = gr.Button(
                    "🎙️ Dùng giọng có sẵn: Ngọc Huyền (ví dụ chính thức từ VieNeu-TTS)",
                    variant="secondary",
                )
                btn_clone_preview = gr.Button("🔊 Nhân bản & Nghe thử", variant="secondary")
                clone_preview_audio = gr.Audio(label="Bản đọc thử (giọng nhân bản)", elem_id="clone_preview_player")
                clone_status = gr.Textbox(label="Trạng thái", interactive=False)
                btn_confirm_clone = gr.Button("✅ Xác nhận dùng giọng nhân bản này", variant="primary")

                cloned_voice_state = gr.State(None)

                btn_ngoc_huyen.click(
                    fn=fetch_ngoc_huyen_sample, outputs=[clone_audio, clone_ref_text, clone_status],
                )
                btn_clone_preview.click(
                    fn=clone_and_preview, inputs=[clone_audio, clone_ref_text],
                    outputs=[cloned_voice_state, clone_preview_audio, clone_status],
                )
                btn_confirm_clone.click(
                    fn=confirm_cloned_voice, inputs=[cloned_voice_state], outputs=[voice_status, tabs],
                )

        # ========== BƯỚC 2 ==========
        with gr.Tab("② Nghe mẫu", id=1):
            gr.Markdown("### Tạo bản đọc thử để kiểm tra giọng đã chọn")
            btn_sample = gr.Button("🎤 Tạo bản mẫu", variant="primary")
            sample_audio = gr.Audio(label="Bản mẫu", elem_id="sample_player")
            speed_selector = gr.Dropdown(
                label="🔊 Tốc độ phát",
                choices=["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "1.75x", "2.0x"],
                value="1.0x",
                interactive=True
            )
            sample_status = gr.Textbox(label="Trạng thái", interactive=False)

            speed_selector.change(
                fn=lambda s: f"✅ Tốc độ: {s}",
                inputs=speed_selector,
                outputs=sample_status,
                js="""(speed) => {
                    window.currentSpeed = parseFloat(speed);
                    const apply = () => {
                        const audios = document.querySelectorAll('#sample_player audio');
                        audios.forEach(a => { a.playbackRate = window.currentSpeed; });
                    };
                    apply();
                    let count = 0;
                    const itv = setInterval(() => { apply(); if(++count > 12) clearInterval(itv); }, 250);
                    return speed;
                }"""
            )

            btn_sample.click(
                fn=generate_sample,
                outputs=[sample_audio, sample_status],
                js="""() => {
                    const itv = setInterval(() => {
                        const audios = document.querySelectorAll('#sample_player audio');
                        if (audios.length > 0) {
                            audios.forEach(a => { a.playbackRate = window.currentSpeed || 1.0; });
                            clearInterval(itv);
                        }
                    }, 500);
                    setTimeout(() => clearInterval(itv), 10000);
                }"""
            )

        # ========== BƯỚC 3: BATCH — RENDER AUDIO -> VIDEO TỰ ĐỘNG ==========
        with gr.Tab("③ Render → Video (Batch)", id=2):
            gr.Markdown("### Upload nhiều file .txt chương truyện — render audio, ghép, tạo phụ đề và xuất video cho từng chương liên tục, không cần thao tác giữa chừng.")
            gr.Markdown("*Chương đã xử lý xong (đã có video, hoặc đã có audio+phụ đề nếu không dùng ảnh nền) sẽ tự động được bỏ qua ở lần chạy sau — an toàn để bấm chạy lại hoặc để máy chạy qua đêm.*")

            batch_input_files = gr.File(
                label="File(s) chương truyện (.txt / .docx) — có thể chọn nhiều file cùng lúc",
                file_types=[".txt", ".docx"], file_count="multiple",
            )

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("#### 📂 Ảnh nền video")
                    batch_bg_image = gr.File(
                        label="🖼️ Ảnh nền (jpg/png, dùng chung cho mọi chương). Để trống = chỉ render audio + phụ đề, không tạo video.",
                        file_types=[".jpg", ".jpeg", ".png"],
                    )
                with gr.Column(scale=1):
                    gr.Markdown("#### ⚙️ Tuỳ chỉnh (dùng chung cho mọi chương)")
                    batch_bgm = gr.File(label="🎵 Nhạc nền BGM (tuỳ chọn)", file_types=[".mp3", ".wav"])
                    batch_bgm_vol = gr.Slider(label="Âm lượng BGM", minimum=0.01, maximum=0.2, value=0.05, step=0.01)
                    batch_silence = gr.Slider(label="Khoảng lặng giữa các phần (giây)", minimum=0.1, maximum=3.0, value=0.5, step=0.1)
                    batch_font = gr.Slider(label="Cỡ chữ phụ đề", minimum=14, maximum=40, value=24, step=1)
                    batch_burn_subs = gr.Checkbox(
                        value=True, label="🔥 Ghi cứng phụ đề vào video",
                        info="Tắt để render NHANH HƠN NHIỀU (bỏ qua bước tốn thời gian nhất) — dùng khi bạn tự upload file .srt riêng lên YouTube (Video > Phụ đề) thay vì ghi cứng vào hình.",
                    )
                    batch_run_delta = gr.Checkbox(
                        value=False, label="🧪 Chạy Agent Delta (QA đối chiếu ASR) — THỬ NGHIỆM",
                        info=(
                            "TẮT theo mặc định. Delta dùng faster-whisper để tự \"nghe lại\" audio vừa render rồi so "
                            "với văn bản gốc, tính ra Word Error Rate — đây CHỈ là 1 tín hiệu tham khảo THÊM, KHÔNG "
                            "thay thế việc bạn tự nghe kiểm tra. Độ chính xác chưa được kiểm chứng kỹ và bản thân "
                            "ASR cũng có thể nghe sai giọng đọc tiếng Việt (lỗi báo ra chưa chắc do audio TTS có vấn "
                            "đề thật). Bật lên sẽ làm batch chạy CHẬM HƠN (thêm 1 lượt nhận dạng giọng nói mỗi "
                            "chương) và cần đã cài faster-whisper/jiwer."
                        ),
                    )

            btn_batch = gr.Button("🌙 Chạy Batch: Audio → Video cho tất cả file", variant="primary", size="lg")
            batch_log = gr.Textbox(label="Nhật ký Batch", lines=20, interactive=False)
            gr.Markdown("---")
            gr.Markdown("### 🎥 Video đã hoàn thành")
            batch_videos = gr.File(label="Tải video (.mp4)", file_count="multiple", interactive=False)

            gr.Markdown("---")
            gr.Markdown("### 📖 Duyệt Glossary (Agent Beta)")
            gr.Markdown(
                "*Thuật ngữ/tên riêng MỚI mà Agent Beta phát hiện trong lần Batch vừa chạy — CHƯA được ghi vào "
                "Character Glossary. Sửa Canonical Form/Entity Type trực tiếp trên bảng nếu cần, xoá dòng nào "
                "không muốn dùng, rồi bấm Duyệt. Chỉ sau khi duyệt, các chương SAU (lần chạy Batch tiếp theo) mới "
                "tự động dùng đúng cách viết này — Agent Beta không bao giờ tự ý thêm vào glossary.*"
            )
            glossary_candidates_table = gr.Dataframe(
                headers=["Term", "Entity Type", "Canonical Form", "Confidence", "Chương phát hiện"],
                datatype=["str", "str", "str", "number", "number"],
                # col_count (KHONG PHAI column_count) - pyproject.toml ghim
                # "gradio>=5.49.1" khong co tran, nen moi truong .venv that
                # su (qua uv sync) se lay dung BAN TOI THIEU 5.49.1, noi
                # tham so con ten "col_count" (chua doi ten). "column_count"
                # chi ton tai tu Gradio 6.x - dung nham no gay
                # "TypeError: Dataframe.__init__() got an unexpected keyword
                # argument" ngay khi khoi dong (loi that, phat hien qua
                # chay run.bat that, khong phai doan mo hinh). "col_count"
                # van hoat dong binh thuong tren ca 5.x lan 6.x (chi bi
                # canh bao deprecated tren 6.x, khong loi) nen an toan hon.
                row_count=(0, "dynamic"), col_count=(5, "fixed"), interactive=True,
                label="Thuật ngữ mới chờ duyệt",
            )
            btn_approve_glossary = gr.Button("✅ Duyệt & Lưu vào Glossary", variant="primary")
            glossary_approve_status = gr.Textbox(label="Trạng thái", interactive=False)
            btn_approve_glossary.click(
                fn=approve_glossary_candidates,
                inputs=[glossary_candidates_table],
                outputs=[glossary_approve_status, glossary_candidates_table],
            )

            btn_batch.click(
                fn=process_batch,
                inputs=[batch_input_files, batch_bgm, batch_bgm_vol, batch_silence, batch_bg_image, batch_font,
                        batch_burn_subs, batch_run_delta],
                outputs=[batch_log, batch_videos, glossary_candidates_table]
            )

            gr.Markdown("---")
            with gr.Accordion("🩺 Kiểm tra sức khoẻ toàn bộ outputs/ (chương nào đang thiếu file)", open=False):
                gr.Markdown("*Quét lại mọi chương đã từng render — kể cả những chương KHÔNG có trong lần chạy batch này — để phát hiện chương còn thiếu audio/phụ đề (báo cáo này cũng tự chạy sau mỗi lần Batch ở trên).*")
                btn_health = gr.Button("🩺 Kiểm tra ngay", variant="secondary")
                health_report = gr.Textbox(label="Báo cáo", lines=12, interactive=False)
                btn_health.click(fn=scan_output_health, outputs=[health_report])

if __name__ == "__main__":
    # server_name="0.0.0.0" + $PORT: bắt buộc để chạy trên Cloud Run (container
    # chỉ nhận traffic tới cổng đọc từ biến môi trường PORT do platform cấp,
    # không phải cổng cố định) — xem Dockerfile ở repo root. Mặc định 7860
    # khi chạy local (không có PORT) để không đổi hành vi hiện tại.
    #
    # _frontend=False: Gradio tự kiểm tra "http://localhost:{port}/" sau khi
    # khởi động (networking.url_ok) để chắc chắn server thật sự chạy được —
    # trong sandbox của Cloud Run, "localhost" phân giải sang IPv6 ::1 trong
    # khi server chỉ lắng nghe wildcard IPv4 0.0.0.0, nên tự-kiểm-tra này LUÔN
    # thất bại (dù server hoàn toàn bình thường — chính Cloud Run tự kiểm tra
    # TCP riêng và xác nhận thành công) → Gradio ném ValueError "When
    # localhost is not accessible..." và container crash ngay. Cloud Run đã
    # tự có health check TCP riêng nên không cần Gradio kiểm tra lại.
    # pwa=True: bật hỗ trợ PWA có sẵn của Gradio (tự sinh manifest, không cần
    # tự viết service worker/manifest.json) — cho phép "Install app" trên
    # trình duyệt khi truy cập qua domain riêng (xem Section 11.7 của spec:
    # bản Cloud Run phụ dùng để chứng minh khả năng deploy công khai qua PWA
    # + domain riêng). Áp dụng chung cho cả 2 môi trường (local + Cloud Run)
    # vì vô hại khi chạy local — Gradio chỉ thêm route/manifest, không đổi gì
    # khác. favicon_path dùng đường dẫn tuyệt đối (nhất quán với current_dir/
    # project_root đã tính ở đầu file) thay vì "./assets/..." tương đối theo
    # CWD như ví dụ trong spec — tránh vỡ nếu chạy từ thư mục khác. Icon hiện
    # tại chỉ là placeholder do Claude tự tạo — CẦN được đội ngũ thay bằng
    # icon thật trước khi nộp bài.
    favicon_path = os.path.join(project_root, "assets", "voxdirector_icon.png")
    app.launch(
        server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)),
        _frontend=False,
        pwa=True, favicon_path=favicon_path if os.path.isfile(favicon_path) else None,
    )
