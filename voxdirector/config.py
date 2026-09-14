"""Cấu hình dùng chung cho toàn bộ VoxDirector AI (v5: 3 Agent — Alpha, Beta
(gộp terminology + expression + pause sentinel), Gamma (QA))."""

import json
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

# 2026-09-14 - "Model resilience" (muc 17 cua master plan
# ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md): danh sach model du phong,
# THU THEO DUNG THU TU, CHI khi GEMINI_MODEL chinh khong con dung duoc
# (ClientError 404 - model bi go bo/doi ten, hoac het luot retry 5xx). Viec
# chon model nay CHI xay ra 1 LAN cho ca tien trinh backend, luc lan goi
# call_structured() DAU TIEN thuc su chay (xem llm_client._resolve_model()) -
# KHONG bao gio doi model GIUA CAC LAN GOI trong CUNG 1 job dang chay, dung
# nguyen tac "1 model ghim cung/lan chay de tai lap duoc" da ghi o
# GEMINI_MODEL o tren. Rong theo mac dinh - DANH SACH MODEL GEMINI THAT SU
# CON DUOC CAP hien tai phai do NGUOI DUNG tu xac nhan qua
# aistudio.google.com (khong the doan/bia ten model o day - dua vao 1 model
# khong ton tai se khien chinh co che fallback nay tro thanh nguyen nhan loi
# moi, thay vi giai phap).
GEMINI_MODEL_FALLBACKS = [
    m.strip()
    for m in os.environ.get("VOXDIRECTOR_GEMINI_MODEL_FALLBACKS", "").split(",")
    if m.strip()
]

# API key đọc từ biến môi trường — KHÔNG hardcode key trong code.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

# NGUYEN NHAN CUA LOI "chi doc duoc ~80% noi dung roi dung hoan toan" (bao
# cao 2026-09-12, xac nhan qua doc code voxdirector/llm_client.py): TRUOC
# ban sua nay, GenerateContentConfig KHONG dat max_output_tokens tuong minh,
# nen SDK dung gia tri mac dinh (thap hon nhieu so voi gioi han that su cua
# model). Agent Beta (va Agent Alpha khi ca 1 cuon truyen dai khong co
# heading "Chuong N" ro rang bi gop thanh 1 chuong DUY NHAT) phai "doc lai"
# GAN NHU TOAN BO van ban goc trong field corrected_text/chapters cua 1 lan
# goi Gemini DUY NHAT - voi van ban dai, output nay CHAM tran gioi han mac
# dinh giua chung, khien response bi CAT NGANG. Vi day la JSON mode
# (response_schema), phan JSON con lai van co the "dep" ve mat cu phap (SDK
# tu dong dong ngoac) nhung NOI DUNG BI THIEU - khong nem loi, pipeline am
# tham chay tiep voi du lieu cut, dung y het trieu chung nguoi dung bao cao.
# Sua: (1) dat max_output_tokens tuong minh o muc CAO (xem llm_client.py),
# (2) kiem tra finish_reason == MAX_TOKENS va bao loi RO RANG thay vi im
# lang dung du lieu thieu (xem llm_client.call_structured()).
GEMINI_MAX_OUTPUT_TOKENS = int(os.environ.get("VOXDIRECTOR_GEMINI_MAX_OUTPUT_TOKENS", "65536"))

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

# Phase 4 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Gamma: tu bao
# cao den tu sua loi"). GIA TRI TAM THOI, CHUA CHOT (giong tinh than
# ALPHA_WINDOW_CHARS/BETA_CHUNK_CHARS) - hieu chuan that su can bo eval set
# co cham diem nguoi that (data/eval_set/, hien con rong - xem README o do),
# chua the lam ngay; 3 hang so nay lam cho nguong gan co MINH BACH VA CHINH
# SUA DUOC qua env var, thay vi 1.5 nam cung trong code nhu truoc.
#
# GAMMA_FLAG_CUTOFF_MULTIPLIER: 1 chunk bi gan co neu WER > overall_wer *
# he so nay (giu nguyen 1.5 da dung tu truoc, chi rut ra thanh config).
# GAMMA_WORD_CONFIDENCE_THRESHOLD: bat ky tu nao ASR bao do tin cay
# (probability, tu faster-whisper word_timestamps) duoi nguong nay cung
# khien chunk bi gan co - NGAY CA KHI WER tong the van chap nhan duoc (1 tu
# nuot mat co the khong lam WER tong the vuot nguong neu chunk du dai).
# GAMMA_MAX_RETRIES: so lan tu dong tong hop lai toi da cho 1 chunk bi gan
# co truoc khi chiu thua va de nguoi dung tu render lai thu cong.
#
# 2026-09-13 - GAMMA_WORD_CONFIDENCE_THRESHOLD HA TU 0.35 XUONG 0.15, XAC
# NHAN CO THAT qua 1 lan chay that cua nguoi dung tren 1 chuong 2013 tu:
# 4/5 chunk bi gan co (chu khong phai thieu so hiem gap nhu ky vong) - lam
# QA cham bat thuong (~5 phut/chuong nho tren CPU) vi retry-and-pick-best
# (Phase 4 muc 13) chay lai cho GAN NHU MOI chunk. 0.35 qua nhay - faster-
# whisper "medium" tren tieng Viet bao ty le tin cay duoi 35% cho kha nhieu
# tu DUNG (khong phai nuot am that), khong phai chi loi that su. 0.15 bat
# LOI RO RET hon (tu ASR gan nhu chac chan sai), giam bao dong gia trong
# khi van giu duoc kha nang bat loi nuot tu that su - VAN LA GIA TRI TAM
# THOI CHUA CHOT, can bo eval set that de hieu chuan chinh xac (xem ghi chu
# tren) - chi la it bao dong hon so voi 0.35 ban dau, khong phai da toi uu.
GAMMA_FLAG_CUTOFF_MULTIPLIER = float(os.environ.get("VOXDIRECTOR_GAMMA_FLAG_CUTOFF_MULTIPLIER", "1.5"))
GAMMA_WORD_CONFIDENCE_THRESHOLD = float(os.environ.get("VOXDIRECTOR_GAMMA_WORD_CONFIDENCE_THRESHOLD", "0.15"))
GAMMA_MAX_RETRIES = int(os.environ.get("VOXDIRECTOR_GAMMA_MAX_RETRIES", "2"))

# 2026-09-14 - "Audio-health checks" (muc 16 cua master plan): kiem tra CHI
# BANG CODE tren chinh song am (khong lien quan ASR/Gemini) - clipping (mat
# tieng do bien do vuot gioi han bieu dien so), khoang lang bat thuong BEN
# TRONG 1 doan (dau hieu TTS "cam" giua chung roi tao ra khoang trong), va
# ca doan gan nhu im lang hoan toan (dau hieu TTS that bai am tham, tra ve
# audio gan nhu rong thay vi loi ro rang). GIA TRI TAM THOI, CHUA CHOT - cung
# tinh than voi GAMMA_FLAG_CUTOFF_MULTIPLIER o tren, can nghe that + bo eval
# set de hieu chuan chinh xac; dat o day de MINH BACH + SUA duoc qua env var
# thay vi hardcode sau trong ham.
#
# GAMMA_AUDIO_CLIP_SAMPLE_RATIO: ty le mau (0-1) cham/gan cham bien do toi da
# (|sample| >= 0.999 sau khi chuan hoa ve [-1, 1]) truoc khi coi ca file la
# "co clipping" - 1 vai mau don le cham dinh la binh thuong (dinh am thanh
# that), phai chiem 1 ty le dang ke moi la dau hieu bi cat am that su.
GAMMA_AUDIO_CLIP_SAMPLE_RATIO = float(os.environ.get("VOXDIRECTOR_GAMMA_AUDIO_CLIP_SAMPLE_RATIO", "0.001"))
# GAMMA_AUDIO_SILENCE_AMPLITUDE: bien do (0-1, sau chuan hoa) duoi nguong nay
# duoc coi la "im lang" khi quet timeline theo cua so nho (xem
# gamma_qa._silence_windows()).
GAMMA_AUDIO_SILENCE_AMPLITUDE = float(os.environ.get("VOXDIRECTOR_GAMMA_AUDIO_SILENCE_AMPLITUDE", "0.01"))
# GAMMA_AUDIO_MAX_INTERNAL_SILENCE_S: 1 khoang lang lien tuc BEN TRONG audio
# (khong phai o dau/cuoi file) dai hon nguong nay (giay) bi gan co la bat
# thuong - 1 cau/doan van dang doc khong nen co khoang trong dai co chu dich
# nhu vay giua chung.
GAMMA_AUDIO_MAX_INTERNAL_SILENCE_S = float(os.environ.get("VOXDIRECTOR_GAMMA_AUDIO_MAX_INTERNAL_SILENCE_S", "1.5"))
# GAMMA_AUDIO_NEAR_SILENT_RMS: RMS (0-1, sau chuan hoa) toan bo file duoi
# nguong nay bi coi la "gan nhu im lang hoan toan" - dau hieu TTS that bai
# am tham (tra ve audio gan nhu rong) hon la 1 doan hop le nhung nho tieng.
GAMMA_AUDIO_NEAR_SILENT_RMS = float(os.environ.get("VOXDIRECTOR_GAMMA_AUDIO_NEAR_SILENT_RMS", "0.005"))

# Sentinel dùng bởi Alpha (đánh dấu điểm cần ngắt kịch tính dài) + Beta (chèn
# vào text) + text_splitter.py (ép làm ranh giới chunk) + audio_postprocess.py
# (áp khoảng lặng dài tại đó) — Section 7.2 của spec. Đây LÀ hằng số kỹ thuật
# cố định trong code, KHÔNG phải dữ liệu do đội ngũ tải lên như
# data/punctuation_pauses.json (Section 7.3, dấu câu thường, ngắn hơn nhiều)
# — 2 cơ chế khác nhau, không dùng chung 1 nguồn cấu hình. Định nghĩa 1 nơi
# duy nhất để text_splitter.py và audio_postprocess.py khớp đúng cùng 1
# chuỗi, tránh lệch nhau nếu sửa ở 1 nơi mà quên nơi kia.
PAUSE_LONG_TOKEN = "[[PAUSE_LONG]]"

# GIÁ TRỊ TẠM THỜI, CHƯA CHỐT — Section 13 (Open Decisions) của spec: đề
# xuất 1200-1500ms (so với ~300-500ms mặc định của khoảng lặng thường), cần
# đội ngũ nghe thật rồi tinh chỉnh lại. Lấy giá trị giữa khoảng đề xuất làm
# điểm khởi đầu, không phải con số đã được xác nhận qua nghe thật.
PAUSE_LONG_DURATION_MS = 1400

# Phase 2 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Map-reduce
# restructure cho tieu thuyet dai") - Alpha chia raw_text thanh cac cua so
# (window) chong lan nhau khi van ban vuot qua nguong nay, thay vi 1 lan goi
# duy nhat khong gioi han (chua tung duoc kiem chung voi tieu thuyet dai
# that su 50k+ tu). GIA TRI TAM THOI, CHUA CHOT - can nguoi that doc thu ket
# qua tach chuong tren 1 cuon dai that de tinh chinh, giong tinh than
# PAUSE_LONG_DURATION_MS o tren. Khi raw_text <= nguong nay, pipeline chi co
# DUNG 1 cua so (= toan bo van ban) - hanh vi giong het truoc day, khong co
# thay doi cho van ban ngan/binh thuong da kiem chung qua Phase 0/1.
ALPHA_WINDOW_CHARS = int(os.environ.get("VOXDIRECTOR_ALPHA_WINDOW_CHARS", "30000"))
ALPHA_WINDOW_OVERLAP_CHARS = int(os.environ.get("VOXDIRECTOR_ALPHA_WINDOW_OVERLAP_CHARS", "3000"))

# Phase 3 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Beta: chunk
# oversized chapters") - CO CHU DICH nho hon ALPHA_WINDOW_CHARS: tran nhan
# thuc that su cua Beta chat hon Alpha nhieu - Beta phai ECHO LAI GAN NHU
# TOAN BO chapter_text trong corrected_text (Alpha chi tra ve index/trich
# dan ngan), nen output token can dung TI LE THUAN voi input, khong chi
# vai chuc index nhu Alpha. Chua tung duoc kiem chung voi 1 chuong that su
# dai - GIA TRI TAM THOI, CHUA CHOT, giong tinh than ALPHA_WINDOW_CHARS o
# tren. chapter_text <= nguong nay -> DUNG 1 chunk (= toan bo chuong) -
# hanh vi giong het truoc Phase 3, khong thay doi cho chuong ngan/binh
# thuong da kiem chung qua Phase 0-2.
BETA_CHUNK_CHARS = int(os.environ.get("VOXDIRECTOR_BETA_CHUNK_CHARS", "12000"))

# TTS engine (2026-09-11: dao nguoc quyet dinh dung Piper, quay lai
# VieNeu-TTS). GHIM CHINH XAC version, khong dung constraint long (>=) - xac
# nhan co THAT (2026-09-11): venv CHUNG cua repo nay co san 1 ban `vieneu`
# EDITABLE INSTALL tro vao src/vieneu/ cua CHINH repo (SDK rieng, kien truc
# CU, version 2.7.0, API hoan toan khac ban PyPI that su can dung). Neu
# khong ghim version + kiem tra o backend startup, mot lan cai dat/venv sai
# se AM THAM dung nham ban local cu thay vi ban PyPI dung README - day CHINH
# LA loi da xay ra va duoc phat hien lai o buoc nay. Xem
# backend/app/main.py (kiem tra version luc startup) va
# pipeline/vieneu_tts.py (module wiring that).
EXPECTED_VIENEU_VERSION = "3.6.4"

# Đường dẫn tới các file dữ liệu config-driven (KHÔNG hardcode danh sách
# giọng/genre trực tiếp trong code Agent hay frontend — xem
# data/voice_presets.json). Đổi TTS engine sau này chỉ cần sửa file JSON này,
# không cần sửa code Alpha/frontend.
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
VOICE_PRESETS_PATH = os.path.join(DATA_DIR, "voice_presets.json")
EMOTION_LEXICON_PATH = os.path.join(DATA_DIR, "emotion_lexicon.json")
GLOSSARY_SEED_PATH = os.path.join(DATA_DIR, "glossary_seed.json")
# Muc 18 cua master plan (uoc tinh chi phi/job, xem voxdirector/usage_tracker.py
# + estimate_cost_usd() ben duoi) - bang gia $/1 trieu token THEO TUNG MODEL,
# team tu dien qua sua truc tiep file JSON (KHONG qua UI Cai dat du lieu nhu 3
# file kia - day la thong so hiem khi doi, khac voi glossary/emotion lexicon
# can sua thuong xuyen). PLACEHOLDER rong ($0) mac dinh - gia Gemini THAT SU
# tai thoi diem dung phai do nguoi dung tu dien tu trang gia chinh thuc cua
# Google, KHONG the doan/bia (gia thay doi theo thoi gian va theo model, bia
# ra se cho ra 1 con so uoc tinh SAI trong khi trong ra dung, con nguy hiem
# hon la khong hien thi gi).
GEMINI_PRICING_PATH = os.path.join(DATA_DIR, "gemini_pricing.json")

# Phase 1 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Persistence &
# measurement"): SQLite job/trace log - ghi chi so (khong phai audio/text day
# du) tung agent moi job, song sot qua restart backend. Cung 1 mo hinh voi
# CHROMA_PERSIST_DIR o tren (thu muc rieng trong voxdirector/, co the gan
# volume Docker rieng, khong dung chung ha tang moi/them dependency ngoai
# sqlite3 co san trong Python).
DB_PATH = os.environ.get(
    "VOXDIRECTOR_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".data", "voxdirector.db"),
)

_cached_voice_presets = None
_cached_emotion_lexicon = None


def load_voice_presets(path=None):
    """Nạp danh sách giọng + bảng genre->voice từ data/voice_presets.json
    (có cache trong tiến trình khi dùng đường dẫn mặc định). Trả về dict với
    2 key: "voices" (list) và "genre_to_voice" (dict genre -> voice id).

    Voice IDs la giong that cua VieNeu-TTS v3 Turbo (23 preset, xac nhan qua
    vieneu.list_preset_voices() - xem _note trong file JSON). genre_to_voice
    la FIRST PASS dua tren "style" (Phong cach) co san cua tung giong -
    KHONG phai gia tri da chot qua nghe that, can review lai bang tai (xem
    _note trong file JSON de biet ly do chon)."""
    global _cached_voice_presets
    if path is None and _cached_voice_presets is not None:
        return _cached_voice_presets
    load_path = path or VOICE_PRESETS_PATH
    with open(load_path, "r", encoding="utf-8") as f:
        presets = json.load(f)
    if path is None:
        _cached_voice_presets = presets
    return presets


def load_emotion_lexicon(path=None):
    """Nạp bảng emotion_label -> list các từ biểu cảm ứng viên từ
    data/emotion_lexicon.json (Section 6.3 cua spec — team-uploaded, KHONG
    hardcode trong Agent). Alpha dùng tập nhãn (key) để biết nhãn nào được
    phép gắn cờ; Beta chọn 1 từ trong danh sách của đúng nhãn khi chèn từ
    biểu cảm — không tự bịa từ ngoài danh sách này.

    Có cache trong tiến trình khi dùng đường dẫn mặc định, giống
    load_voice_presets()."""
    global _cached_emotion_lexicon
    if path is None and _cached_emotion_lexicon is not None:
        return _cached_emotion_lexicon
    load_path = path or EMOTION_LEXICON_PATH
    with open(load_path, "r", encoding="utf-8") as f:
        lexicon = json.load(f)
    if path is None:
        _cached_emotion_lexicon = lexicon
    return lexicon


def invalidate_emotion_lexicon_cache() -> None:
    """Xoa cache trong tien trinh - goi ngay sau khi POST /api/settings/emotion-lexicon
    (backend/app/main.py) ghi de file, de load_emotion_lexicon() doc lai TU
    DIA o lan goi ke tiep thay vi tra ve ban cu da cache. XAC NHAN CO THAT
    qua bao cao nguoi dung (2026-09-13): truoc ban sua nay, sua Cai dat du
    lieu tren UI luu file dung nhung KHONG anh huong gi toi pipeline dang
    chay cho toi khi restart backend thu cong - loi ngam, khong bao loi ro
    rang cho nguoi dung biet.

    LUU Y con lai (KHONG sua duoc bang cache invalidation don thuan): tap
    NHAN (label) hop le - "cuoi"/"tho_dai"/"hang_giong" - duoc dung de xay
    kieu Literal cua Pydantic (EmotionLabel trong alpha_ingestion.py/
    beta_consistency.py) ngay luc MODULE duoc import, dung de ep schema dau
    ra cua Gemini. Sua NOI DUNG danh sach tu cho 1 nhan DA CO se co hieu luc
    ngay (xem run_beta() da doc lai load_emotion_lexicon() moi lan goi thay
    vi dung bien dong cung module) - nhung THEM/XOA hang nhan hoan toan moi
    van can restart backend, vi kieu Pydantic khong tu doi lai duoc."""
    global _cached_emotion_lexicon
    _cached_emotion_lexicon = None


_cached_gemini_pricing = None


def load_gemini_pricing(path=None) -> dict:
    """Nap bang gia $/1 trieu token theo model tu data/gemini_pricing.json -
    xem chu thich day du o GEMINI_PRICING_PATH. Model khong co trong file
    (hoac file khong ton tai) tra ve None cho model do khi tra cuu qua
    estimate_cost_usd() - KHONG tu gan gia $0 (nhin giong "mien phi da xac
    nhan" trong khi that ra la "chua cau hinh")."""
    global _cached_gemini_pricing
    if path is None and _cached_gemini_pricing is not None:
        return _cached_gemini_pricing
    load_path = path or GEMINI_PRICING_PATH
    try:
        with open(load_path, "r", encoding="utf-8") as f:
            pricing = json.load(f)
    except FileNotFoundError:
        pricing = {}
    if path is None:
        _cached_gemini_pricing = pricing
    return pricing


def invalidate_gemini_pricing_cache() -> None:
    """Xem invalidate_emotion_lexicon_cache() o tren - cung co che, du file
    gia hien khong co endpoint Settings UI rieng (sua truc tiep tren dia)."""
    global _cached_gemini_pricing
    _cached_gemini_pricing = None


def estimate_cost_usd(model: str, prompt_tokens: int, output_tokens: int) -> float | None:
    """Quy doi so token THAT SU da dung (do Gemini API tra ve, xem
    voxdirector/usage_tracker.py) ra USD theo gia da cau hinh cho DUNG model
    da dung. Tra ve None (khong phai 0.0) neu model nay chua co trong bang gia
    - phan biet ro "chua biet gia" voi "gia = 0"."""
    pricing = load_gemini_pricing()
    rate = pricing.get(model)
    if not rate:
        return None
    input_rate = rate.get("input_per_1m_tokens_usd")
    output_rate = rate.get("output_per_1m_tokens_usd")
    if input_rate is None or output_rate is None:
        return None
    return (prompt_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
