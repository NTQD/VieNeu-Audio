"""FastAPI backend - WIRING THAT (Step 9 cua build order, Section 11 cua
spec) - Alpha -> Beta -> normalizer -> splitter -> TTS -> postprocess ->
subtitle -> Gamma QA (tuy chon, Step 11).

Chay dong bo, 1 tien trinh, JOBS luu trong bo nho (dict) - dung pham vi
"local end-to-end test" (Step 14), KHONG phai production nhieu-user-dong-
thoi (se can hang doi/worker + persistent store rieng, ngoai pham vi build
order hien tai).

Video rendering (2026-09-12 - noi vao theo yeu cau nguoi dung "dieu kien de
nut Xuat Video hoat dong la co anh nen"): pipeline/video_renderer.py da viet
san day du (auto-do GPU encoder, fallback libx264, burn subtitle tuy chon)
nhung CHUA TUNG duoc goi truoc ban sua nay. Video CHI duoc render khi nguoi
dung co upload anh nen qua POST /api/background-image/{job_id} - khong co
anh thi job van chi co audio/subtitle nhu truoc, dung y disable mac dinh cua
nut "Xuat Video" o frontend.
"""
import asyncio
import json
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import sys as _sys
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent.parent
if str(PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
VOICE_PRESETS_PATH = DATA_DIR / "voice_presets.json"
EMOTION_LEXICON_PATH = DATA_DIR / "emotion_lexicon.json"
GLOSSARY_SEED_PATH = DATA_DIR / "glossary_seed.json"
PUNCTUATION_PAUSES_PATH = DATA_DIR / "punctuation_pauses.json"
# 2026-09-12 - "Voice Audition": 23 file .wav TINH, tao san 1 lan qua
# scripts/generate_voice_previews.py (VieNeu-TTS khong co san preview audio
# nhu ElevenLabs - phai tu tong hop) - KHONG sinh luc chay.
VOICE_PREVIEWS_DIR = DATA_DIR / "voice_previews"

JOBS_DIR = APP_DIR / "_jobs"
JOBS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="VoxDirector AI backend")


@app.on_event("startup")
def _check_vieneu_version():
    """Fail LOUD (khong tiep tuc chay) neu version `vieneu` dang cai KHONG
    khop ban da ghim trong voxdirector.config.EXPECTED_VIENEU_VERSION - bao
    hiem re cho dung 1 loi da xay ra that (2026-09-11): venv chung cua repo
    co san 1 ban `vieneu` editable-install khac hoan toan (kien truc cu,
    API khac) tu chinh src/vieneu/ cua repo nay, am tham shadow ban PyPI
    that su can dung neu chay nham venv. Khac voi _seed_glossary_if_empty()
    (chi canh bao roi tiep tuc), ham nay CO CHU DICH raise de uvicorn dung
    hoan toan qua trinh khoi dong - sai version TTS engine khong phai loi
    nen "van chay duoc, xu ly sau"."""
    import importlib.metadata

    from voxdirector.config import EXPECTED_VIENEU_VERSION

    try:
        installed = importlib.metadata.version("vieneu")
    except importlib.metadata.PackageNotFoundError:
        raise RuntimeError(
            "Khong tim thay package 'vieneu' trong moi truong Python dang chay backend. "
            "Backend PHAI chay bang venv rieng (backend/.venv) da cai dung "
            f"vieneu=={EXPECTED_VIENEU_VERSION}, xem backend/requirements.txt."
        )

    if installed != EXPECTED_VIENEU_VERSION:
        raise RuntimeError(
            f"vieneu version KHONG khop: dang cai {installed!r}, can dung "
            f"{EXPECTED_VIENEU_VERSION!r} (voxdirector.config.EXPECTED_VIENEU_VERSION). "
            f"Neu day la venv chung cua repo (khong phai backend/.venv rieng), no co the "
            f"dang dung nham ban `vieneu` editable-install cu tro vao src/vieneu/ cua "
            f"chinh repo nay thay vi ban PyPI that."
        )

    print(f"[VoxDirector] vieneu version OK: {installed} (khop EXPECTED_VIENEU_VERSION).")


@app.on_event("startup")
def _seed_glossary_if_empty():
    """Nap data/glossary_seed.json vao ChromaDB 1 lan khi container/volume
    con trong (Step 15 - container fresh khong tu co seed data, khac voi
    may dev da chay seed_from_file() thu cong qua scratch_check truoc do).
    Khong lam gi neu collection da co entry (deploy lai, volume da ton tai)
    - tranh nap trung lap."""
    from voxdirector.glossary.store import _get_collection, seed_from_file

    try:
        collection = _get_collection()
        if collection.count() == 0:
            n = seed_from_file()
            print(f"[VoxDirector] Da nap {n} glossary seed entry (collection rong luc khoi dong).")
    except Exception as e:
        print(f"[VoxDirector] Canh bao: khong nap duoc glossary seed luc khoi dong ({e}) - "
              f"pipeline van chay binh thuong, glossary se trong cho den khi nap thu cong.")


@app.on_event("startup")
def _init_job_db():
    """Phase 1 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md - tao schema
    SQLite job/trace log (voxdirector/db.py) som luc khoi dong, cung mo hinh
    voi _seed_glossary_if_empty() o tren - loi (vd. dia chi doc) khong duoc
    chan uvicorn khoi dong, chi mat kha nang ghi trace."""
    from voxdirector.db import _get_conn

    try:
        _get_conn()
    except Exception as e:
        print(f"[VoxDirector] Canh bao: khong khoi tao duoc job trace DB ({e}) - "
              f"pipeline van chay binh thuong, chi khong co lich su job.")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# job_id -> {raw_text, alpha_result, job_dir}. Trong bo nho - mat khi restart
# server (chap nhan duoc o pham vi local test; xem docstring dau file).
JOBS: dict[str, dict] = {}


@app.get("/api/voices")
def get_voices():
    with open(VOICE_PRESETS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/voice-preview/{voice_id}")
def get_voice_preview(voice_id: str):
    """2026-09-12 - "Voice Audition": tra ve file .wav TINH da tao san (xem
    scripts/generate_voice_previews.py) cho dung giong doc voice_id, dung boi
    VoicePicker luc di chuot qua 1 giong (xem frontend/src/lib/voice-adapter.ts).
    Slug phai KHOP CHINH XAC voi pipeline.voice_naming.slugify_voice_id() -
    dung CHUNG 1 ham voi script tao file de khong bao gio lech ten."""
    from pipeline.voice_naming import slugify_voice_id

    preview_path = VOICE_PREVIEWS_DIR / f"{slugify_voice_id(voice_id)}.wav"
    if not preview_path.is_file():
        raise HTTPException(status_code=404, detail=f"Chưa có preview cho giọng {voice_id!r}")
    return FileResponse(preview_path, media_type="audio/wav")


@app.get("/api/settings/emotion-lexicon")
def get_emotion_lexicon():
    with open(EMOTION_LEXICON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/settings/emotion-lexicon")
def upload_emotion_lexicon(payload: dict):
    with open(EMOTION_LEXICON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    # Xac nhan co THAT qua bao cao nguoi dung (2026-09-13): truoc ban sua
    # nay, luu file xong nhung Beta van dung ban cache cu trong bo nho cho
    # toi khi restart backend thu cong - khong bao loi, chi am tham khong
    # co hieu luc. Xem docstring invalidate_emotion_lexicon_cache() de biet
    # gioi han con lai (them/xoa HANG NHAN moi van can restart).
    from voxdirector.config import invalidate_emotion_lexicon_cache

    invalidate_emotion_lexicon_cache()
    return {"status": "ok", "labels": [k for k in payload if not k.startswith("_")]}


@app.get("/api/settings/glossary-seed")
def get_glossary_seed():
    with open(GLOSSARY_SEED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/settings/glossary-seed")
def upload_glossary_seed(payload: dict):
    with open(GLOSSARY_SEED_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return {"status": "ok", "entry_count": len(payload.get("entries", []))}


@app.get("/api/settings/punctuation-pauses")
def get_punctuation_pauses():
    """Section 7.3 cua spec: "GET /api/settings/punctuation-pauses ... same
    replace-on-upload behavior" nhu emotion-lexicon."""
    with open(PUNCTUATION_PAUSES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/settings/punctuation-pauses")
def upload_punctuation_pauses(payload: dict):
    with open(PUNCTUATION_PAUSES_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    # Cung 1 loi voi emotion-lexicon o tren - xem invalidate_emotion_lexicon_cache().
    # Bang nay khong bi dong bang vao kieu Pydantic Literal nao nen se co
    # hieu luc NGAY, khong con gioi han nao con lai.
    from pipeline.punctuation_pauses import invalidate_cache

    invalidate_cache()
    return {"status": "ok", "keys": [k for k in payload if not k.startswith("_")]}


class SubmitRequest(BaseModel):
    text: str
    # BYOK (Section 13 cua spec, chot 2026-09-10): "users will use their own
    # API key, we use their key for their own use". Gui qua JSON body (KHONG
    # bao gio qua query string/URL - se bi log lai o access log/proxy/lich su
    # trinh duyet). None -> dung GEMINI_API_KEY mac dinh cua server (fallback
    # khi nguoi dung chua nhap key rieng).
    api_key: str | None = None
    # Nut bat/tat Agent Alpha (advanced options, 2026-09-12) - True (mac
    # dinh) = chay that qua Gemini; False = process_submission_fallback()
    # (regex thuan, khong goi Gemini) - xem voxdirector/orchestrator.py.
    alpha_enabled: bool = True


class SubmitResponse(BaseModel):
    job_id: str
    chapters: int
    detected_genre: str
    suggested_voice_id: str
    genre_confidence_score: float
    # Section 5c cua PHASE0_HANDOFF.md - so chuong Alpha danh dau needs_review
    # (ranh gioi tach chuong khong chac chan) - truoc ban sua nay, alpha_result
    # da tinh dung field nay nhung khong bao gio roi khoi backend.
    chapters_needing_review: int
    # Phase 2 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Richer genre
    # signal") - None khi Alpha tat (process_submission_fallback khong tinh
    # duoc, xem voxdirector/orchestrator.py).
    tone: str | None = None
    pacing: str | None = None
    target_audience: str | None = None


@app.post("/api/submit", response_model=SubmitResponse)
def submit(req: SubmitRequest):
    """Section 3 step 2 cua spec: "Submit -> Alpha runs" - goi Alpha THAT
    (Gemini that), dong bo, truoc khi WebSocket cua Beta/TTS/QA bat dau."""
    from voxdirector.orchestrator import process_submission
    from voxdirector import usage_tracker

    api_key = req.api_key.strip() if req.api_key and req.api_key.strip() else None
    # job_id duoc tao O DAY (truoc khi goi Alpha), som hon truoc day (truoc
    # chi tao sau khi Alpha da chay xong) - can co job_id TRUOC lan goi
    # Gemini dau tien cua job nay de usage_tracker biet ghi token cua Alpha
    # vao dung job nao (muc 18 cua master plan, xem voxdirector/usage_tracker.py).
    job_id = str(uuid.uuid4())
    usage_tracker.set_current_job(job_id)
    _alpha_start = time.monotonic()
    try:
        alpha_result = process_submission(req.text, api_key=api_key, alpha_enabled=req.alpha_enabled)
    except Exception as e:
        # Submit that bai hoan toan - khong con job_id nao dung den nua, xoa
        # bo dem token (neu Alpha da thanh cong 1 vai window truoc khi loi -
        # map-reduce nhieu window) de khong ro ri bo nho vinh vien trong
        # usage_tracker._usage_by_job cho 1 job se khong bao gio goi
        # record_job()/clear_job() o noi khac.
        usage_tracker.clear_job(job_id)
        # Loi pho bien nhat voi BYOK la key sai/rong/het quota - tra ve loi
        # ro rang thay vi 500 chung chung, de frontend hien duoc cho nguoi
        # dung biet phai sua gi (thay vi chi thay "that bai"). alpha_enabled
        # False khong goi Gemini (process_submission_fallback, thuan regex) -
        # thong bao loi phai phan biet, khong do oan cho "API key" khi nguyen
        # nhan that su o cho khac.
        if req.alpha_enabled:
            raise HTTPException(
                status_code=400,
                detail=f"Không gọi được Gemini (kiểm tra API key của bạn trong Cài đặt): {e}",
            )
        raise HTTPException(status_code=400, detail=f"Lỗi khi tách chương (Agent Alpha đang TẮT): {e}")
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    # api_key luu KEM job (bo nho, mat khi restart server - cung gioi han
    # nhu raw_text/alpha_result, xem docstring dau file) de WS handler
    # (chay Beta sau do) dung DUNG key nay, khong can nguoi dung gui lai.
    JOBS[job_id] = {
        "raw_text": req.text, "alpha_result": alpha_result, "job_dir": job_dir,
        "api_key": api_key,
        # 2026-09-13 - thoi gian THAT cua Alpha (goi Gemini, neu bat) - dung
        # trong timing_breakdown cua ket qua cuoi, xem ws_progress().
        "alpha_duration_s": round(time.monotonic() - _alpha_start, 1),
        # Phase 1 - can luu lai de ghi vao job trace log (voxdirector/db.py)
        # luc ws_progress() ket thuc; khong the doc lai tu dau vi request POST
        # /api/submit da xong tu lau, chi con query param cua WS biet
        # beta_enabled/qa_enabled.
        "alpha_enabled": req.alpha_enabled,
    }

    return SubmitResponse(
        job_id=job_id,
        chapters=len(alpha_result["chapters"]),
        detected_genre=alpha_result["detected_genre"] or "",
        suggested_voice_id=alpha_result["suggested_voice_id"] or "",
        genre_confidence_score=alpha_result["genre_confidence_score"],
        chapters_needing_review=sum(
            1 for c in alpha_result["chapters"] if c.get("needs_review")
        ),
        tone=alpha_result.get("tone"),
        pacing=alpha_result.get("pacing"),
        target_audience=alpha_result.get("target_audience"),
    )


_VALID_GLOSSARY_ENTITY_TYPES = {"character", "place", "term"}


class GlossaryApproveRequest(BaseModel):
    term: str
    entity_type: str


@app.post("/api/glossary/approve")
def approve_glossary_term(req: GlossaryApproveRequest):
    """Section 5a cua PHASE0_HANDOFF.md - P0: truoc ban sua nay,
    approve_new_entries() (voxdirector/agents/beta_consistency.py) khong bao
    gio duoc goi tu dau ca - nut "Duyet" o frontend chi xoa candidate khoi
    danh sach hien thi, KHONG ghi gi vao glossary that. Endpoint nay la cau
    noi con thieu.

    Khong can job_id - ghi thang vao glossary ChromaDB ben ben, khong gan voi
    1 job cu the (xem docstring approve_new_entries())."""
    from voxdirector.agents.beta_consistency import approve_new_entries

    if req.entity_type not in _VALID_GLOSSARY_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"entity_type không hợp lệ: {req.entity_type!r} (phải là character/place/term)",
        )
    approve_new_entries([{"term": req.term, "entity_type": req.entity_type}])
    return {"status": "ok"}


# 2026-09-14 - "Glossary dang dung" (khac voi "Glossary khoi tao" -
# data/glossary_seed.json, file JSON tinh o Cai dat du lieu): endpoint nay
# doc/ghi TRUC TIEP tren ChromaDB - CHINH LA noi POST /api/glossary/approve o
# tren da ghi vao. Truoc ban sua nay, khong co cach nao xem lai entry da
# duyet o dau ca (Cai dat du lieu chi hien seed file tinh) - nguoi dung bao
# cao "duyet xong nhung khong thay dau" la vi ho dang nhin sai cho, khong
# phai loi ghi du lieu (approve_new_entries() van ghi dung ChromaDB nhu cu).
@app.get("/api/glossary")
def list_glossary_entries():
    from voxdirector.glossary.store import list_entries

    return {"entries": list_entries()}


class GlossaryEntryRequest(BaseModel):
    original_term: str
    entity_type: str
    canonical_form: str
    pronunciation_note: str | None = None
    first_seen_chapter: int | None = None


@app.post("/api/glossary")
def upsert_glossary_entry(req: GlossaryEntryRequest):
    """Them/sua 1 entry TRUC TIEP trong glossary dang dung (khong qua luong
    "candidate can duyet" nhu /api/glossary/approve) - dung khi nguoi dung tu
    go 1 thuat ngu moi qua Glossary manager, hoac sua 1 entry da co san."""
    from voxdirector.glossary.schema import GlossaryEntry
    from voxdirector.glossary.store import add_entry

    if req.entity_type not in _VALID_GLOSSARY_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"entity_type không hợp lệ: {req.entity_type!r} (phải là character/place/term)",
        )
    if not req.original_term.strip() or not req.canonical_form.strip():
        raise HTTPException(status_code=400, detail="original_term và canonical_form không được để trống")
    add_entry(GlossaryEntry(
        original_term=req.original_term,
        entity_type=req.entity_type,
        canonical_form=req.canonical_form,
        pronunciation_note=req.pronunciation_note,
        first_seen_chapter=req.first_seen_chapter,
    ))
    return {"status": "ok"}


@app.delete("/api/glossary/{original_term}")
def delete_glossary_entry(original_term: str):
    from voxdirector.glossary.store import delete_entry

    deleted = delete_entry(original_term)
    return {"status": "ok", "deleted": deleted}


@app.get("/api/glossary/suggest-label")
def suggest_glossary_label(term: str):
    """Goi y entity_type theo tu khoa (khong dung Gemini - xem
    voxdirector/glossary/label_suggestion.py) cho 1 term nguoi dung dang go
    trong Glossary manager, truoc khi ho tu chon/xac nhan loai chinh xac."""
    from voxdirector.glossary.label_suggestion import suggest_entity_type

    return {"term": term, "suggested_entity_type": suggest_entity_type(term)}


@app.post("/api/background-image/{job_id}")
async def upload_background_image(job_id: str, file: UploadFile = File(...)):
    """2026-09-12 - nguoi dung yeu cau "dieu kien de nut Xuat Video hoat dong
    la co anh nen" - anh nen la INPUT BAT BUOC de render_video() (xem
    pipeline/video_renderer.py, da viet san tu truoc nhung CHUA TUNG duoc noi
    vao backend/frontend). Multipart rieng (khong nhet vao /api/submit JSON)
    vi anh la binary, khong hop voi body JSON hien co cua SubmitRequest.

    Goi endpoint nay SAU /api/submit (da co job_id) nhung TRUOC khi mo
    WebSocket - xem ws_progress(): no chi render video NEU
    job["background_image_path"] da ton tai luc chay xong buoc ghep audio."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id không tồn tại")

    ext = os.path.splitext(file.filename or "")[1] or ".png"
    image_path = job["job_dir"] / f"background{ext}"
    with open(image_path, "wb") as f:
        f.write(await file.read())
    job["background_image_path"] = str(image_path)
    return {"status": "ok"}


@app.post("/api/background-music/{job_id}")
async def upload_background_music(job_id: str, file: UploadFile = File(...), volume: float = Form(0.05)):
    """2026-09-14 - Nhac nen (BGM). Cung mo hinh voi upload_background_image()
    o tren: upload SAU /api/submit, TRUOC khi mo WebSocket - ws_progress() chi
    tron BGM vao final.wav NEU job["background_music_path"] da co san luc no
    chay toi buoc ghep audio (xem voxdirector.orchestrator.rebuild_final_audio()).

    XAC NHAN CO THAT qua doc code (khong phai gia dinh): pipeline.audio_postprocess.mix_bgm()
    da duoc VIET SAN tu truoc (dung cho CLI doc lap cua chinh file do) nhung
    CHUA TUNG duoc goi tu backend/frontend - hoan toan giong tinh trang
    render_video() truoc ban sua 2026-09-12 (docstring dau file). "BGM merging
    khong hoat dong" nguoi dung bao cao la vi thieu chinh endpoint nay + lan
    goi ket noi vao ws_progress(), KHONG phai loi trong logic tron am cua
    mix_bgm() (logic do van dung, xem chu thich cua no).

    volume: he so am luong BGM (0-1, form field kem file) - nguoi dung dieu
    chinh qua slider o AdvancedOptions.tsx, mac dinh 0.05 (rat nho, dung y
    "nen am thanh" khong lan at giong doc)."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id không tồn tại")

    ext = os.path.splitext(file.filename or "")[1] or ".mp3"
    music_path = job["job_dir"] / f"background_music{ext}"
    with open(music_path, "wb") as f:
        f.write(await file.read())
    job["background_music_path"] = str(music_path)
    job["bgm_volume"] = volume
    return {"status": "ok"}


@app.get("/api/audio/{job_id}")
def get_audio(job_id: str):
    job = JOBS.get(job_id)
    if not job or "final_audio_path" not in job:
        raise HTTPException(status_code=404, detail="Audio chưa sẵn sàng hoặc job_id không tồn tại")
    return FileResponse(job["final_audio_path"], media_type="audio/wav")


@app.get("/api/video/{job_id}")
def get_video(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("final_video_path"):
        raise HTTPException(
            status_code=404,
            detail="Video chưa sẵn sàng (cần cung cấp ảnh nền trước khi xử lý) hoặc job_id không tồn tại",
        )
    return FileResponse(job["final_video_path"], media_type="video/mp4")


@app.get("/api/subtitles/{job_id}")
def get_subtitles(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("final_srt_path"):
        raise HTTPException(status_code=404, detail="Phụ đề chưa sẵn sàng hoặc job_id không tồn tại")
    return FileResponse(job["final_srt_path"], media_type="text/plain")


STAGES = [
    {"key": "alpha", "label": "Đã phân tích văn bản (Alpha)"},
    {"key": "beta", "label": "Đang áp dụng tính nhất quán & biểu cảm (Beta)"},
    {"key": "tts", "label": "Đang tạo giọng đọc"},
    {"key": "assemble", "label": "Đang ghép audio & phụ đề"},
    {"key": "qa", "label": "Đang kiểm tra chất lượng (Gamma)"},
]


def _pop_gemini_usage_summary(job_id: str) -> dict:
    """Doc TONG token Gemini da dung cho 1 job (Alpha + moi chuong cua Beta/
    QA cong lai, xem voxdirector/usage_tracker.py) roi XOA bo dem cua job do
    (goi 1 lan LUC JOB VUA XONG - thanh cong hoac loi - de khong ro ri bo
    nho). Quy doi ra USD qua config.estimate_cost_usd() cho TUNG model rieng
    da dung (thuong chi 1 model, tru khi model resilience da chuyen model
    giua chung tien trinh backend - xem llm_client._resolve_model()); cost
    tong = None (khong phai 0.0) neu BAT KY model nao trong so do chua co
    gia cau hinh, de khong hien 1 con so SAI (thieu) ma tuong nhu day du."""
    from voxdirector import usage_tracker
    from voxdirector.config import estimate_cost_usd

    totals = usage_tracker.get_totals(job_id)
    usage_tracker.clear_job(job_id)

    cost_total = 0.0
    cost_known = True
    for model, counts in totals["by_model"].items():
        cost = estimate_cost_usd(model, counts["prompt_tokens"], counts["output_tokens"])
        if cost is None:
            cost_known = False
        else:
            cost_total += cost

    return {
        "gemini_prompt_tokens": totals["total_prompt_tokens"],
        "gemini_output_tokens": totals["total_output_tokens"],
        "gemini_by_model": totals["by_model"],
        "estimated_cost_usd": round(cost_total, 6) if cost_known and totals["by_model"] else None,
    }


@app.websocket("/api/ws/{job_id}")
async def ws_progress(websocket: WebSocket, job_id: str):
    """Step 9 (wiring that) + Step 11 (Gamma toggle qua query param
    qa_enabled). voice_id/pause_duration_ms/qa_enabled truyen qua query
    string cua WS handshake (khong the truyen qua POST body cho WS)."""
    await websocket.accept()

    job = JOBS.get(job_id)
    if not job:
        await websocket.send_json({"type": "error", "message": "job_id không tồn tại"})
        await websocket.close()
        return

    # Muc 18 cua master plan (uoc tinh token/chi phi) - dung LAI job_id nay
    # (da duoc set luc /api/submit cho lan goi Alpha) de moi lan goi Gemini
    # cua Beta/QA trong WS session nay cung duoc ghi vao TONG token cua CUNG
    # 1 job (xem voxdirector/usage_tracker.py). asyncio.to_thread() ben duoi
    # copy contextvars cua request nay sang thread moi nen van doc dung.
    from voxdirector import usage_tracker

    usage_tracker.set_current_job(job_id)

    params = websocket.query_params
    voice_id = params.get("voice_id") or job["alpha_result"]["suggested_voice_id"]
    pause_duration_ms = int(params.get("pause_duration_ms", "500"))
    qa_enabled = params.get("qa_enabled", "false").lower() == "true"
    # Nut bat/tat Agent Beta (advanced options, 2026-09-12) - mac dinh True
    # (giu hanh vi cu). False bo qua run_beta() trong process_chapter() cho
    # MOI chuong cua job nay - xem voxdirector/orchestrator.py.
    beta_enabled = params.get("beta_enabled", "true").lower() == "true"
    # Chi anh huong khi CO anh nen (job["background_image_path"], upload qua
    # POST /api/background-image/{job_id} truoc khi mo WS nay) - xem khoi
    # render video ben duoi.
    burn_subtitles = params.get("burn_subtitles", "true").lower() == "true"

    # 2026-09-12 (yeu cau nguoi dung: "them hien thi thoi gian dung file") -
    # do THOI GIAN THAT ma toan bo pipeline (Alpha/Beta/TTS/ghep/video/QA) mat
    # de xu ly xong 1 job, tinh tu luc WS nay bat dau chay - hien o ket qua
    # cuoi de nguoi dung biet job nay "nang" hay "nhe" (huu ich khi so sanh
    # bat/tat Agent nao thi nhanh hon, dung y voi nhan xet cua nguoi dung o
    # tin nhan truoc: "khong dung Agent thi render nhanh hon").
    processing_started_at = time.monotonic()

    try:
        await websocket.send_json({
            "type": "progress", "stage": "alpha", "label": STAGES[0]["label"],
            "stage_index": 0, "total_stages": len(STAGES),
        })

        from voxdirector.orchestrator import process_chapter
        from voxdirector.text_utils import items_for_span

        alpha_result = job["alpha_result"]
        raw_text = job["raw_text"]
        job_dir: Path = job["job_dir"]

        chapter_results = []
        for ci, chapter in enumerate(alpha_result["chapters"]):
            chapter_text = chapter["text"]
            chapter_emotions = items_for_span(alpha_result["emotion_flagged_segments"], chapter_text)
            chapter_pauses = items_for_span(alpha_result["pause_points"], chapter_text)

            for stage_idx, stage_key in [(1, "beta"), (2, "tts"), (3, "assemble")]:
                await websocket.send_json({
                    "type": "progress",
                    "stage": stage_key,
                    "label": f"{STAGES[stage_idx]['label']} (chương {ci + 1}/{len(alpha_result['chapters'])})",
                    "stage_index": stage_idx, "total_stages": len(STAGES),
                })

            chapter_dir = str(job_dir / f"chapter_{ci + 1}")
            # QUAN TRONG: process_chapter() la ham DONG BO, chay Beta (Gemini
            # API that) + TTS + ffmpeg + subtitle - co the mat 20-90+ giay.
            # Goi TRUC TIEP (khong asyncio.to_thread) se CHAN CUNG event loop
            # cua asyncio trong suot thoi gian do, khien uvicorn khong the
            # tra loi WebSocket ping/pong keepalive lan khong gui duoc bat ky
            # progress message nao khac - xac nhan co THAT qua test standalone
            # 2026-09-10 (scratch_check/verified/test_e2e_real.py): ket noi WS bi chinh
            # server dong voi loi "1011 internal error keepalive ping timeout"
            # giua chung, KHONG phai loi cua client. asyncio.to_thread() chay
            # ham dong bo tren 1 thread rieng, tra quyen dieu khien lai cho
            # event loop de no van phuc vu duoc ping/pong + cac request khac.
            result = await asyncio.to_thread(
                process_chapter,
                chapter_text, chapter_emotions, chapter_pauses,
                chapter_dir, f"chapter_{ci + 1}", voice_id,
                pause_duration_ms_default=pause_duration_ms,
                qa_enabled=False,  # QA chay 1 lan cho ca job sau khi ghep, xem duoi
                beta_enabled=beta_enabled,
                chapter_number=ci + 1,
                api_key=job.get("api_key"),  # BYOK - key da luu tu luc /api/submit
            )
            chapter_results.append(result)

            # Phase 1 - ghi trace chuong nay ngay (khong doi ca job xong) de
            # 1 chuong loi giua chung van con lai duoc chi so cua cac chuong
            # da xong truoc do trong DB. Loi ghi trace tu boc rieng trong
            # record_chapter(), khong the lam gian doan vong lap nay.
            from voxdirector.db import record_chapter

            record_chapter(
                job_id=job_id,
                chapter_number=ci + 1,
                alpha_confidence_score=chapter.get("confidence_score"),
                needs_review=chapter.get("needs_review", False),
                emotion_flagged_count=len(chapter_emotions),
                pause_points_count=len(chapter_pauses),
                applied_terms_count=len(result["applied_terms"]),
                new_entry_candidates_count=len(result["new_entry_candidates"]),
                expression_report=result["expression_report"],
                pause_report=result["pause_report"],
                chunk_count=len(result["chunks"]),
                beta_duration_s=result.get("beta_duration_s", 0.0),
                tts_duration_s=result.get("tts_duration_s", 0.0),
            )

        # Ghep audio cac chuong thanh 1 file duy nhat cho ca job (khoang lang
        # 1.0s co dinh giua chuong - khong phai gia tri chot trong spec, chi
        # la lua chon hop ly cho pham vi test noi bo nay). Dung chung ham voi
        # /api/rerender (rebuild_final_audio, tron them BGM neu co - xem
        # docstring ham do) - xem docstring de biet ly do BAT BUOC phai goi
        # lai (KHONG duoc goi assemble_final_audio() truc tiep) sau moi lan
        # re-render 1 segment/QA auto-retry.
        from pipeline.vieneu_tts import get_sample_rate
        from voxdirector.orchestrator import rebuild_final_audio

        sample_rate = get_sample_rate(voice_id)
        final_audio_path = str(job_dir / "final.wav")
        _assemble_start = time.monotonic()
        await asyncio.to_thread(
            rebuild_final_audio, str(job_dir), len(chapter_results), sample_rate, final_audio_path,
            job.get("background_music_path"), job.get("bgm_volume", 0.05),
        )
        assemble_duration_s = time.monotonic() - _assemble_start
        job["final_audio_path"] = final_audio_path

        # Gop subtitle cac chuong (dich timestamp theo cumulative offset).
        final_srt_path = _merge_subtitles(chapter_results, inter_chapter_gap_s=1.0, out_path=str(job_dir / "final.srt"))
        job["final_srt_path"] = final_srt_path

        # Render video (2026-09-12) - CHI khi nguoi dung da upload anh nen qua
        # POST /api/background-image/{job_id} truoc khi mo WS nay. Khong co
        # anh: job van chi co audio/subtitle nhu truoc (dung dieu kien nguoi
        # dung yeu cau: "dieu kien de nut Xuat Video hoat dong la co anh nen").
        background_image_path = job.get("background_image_path")
        video_duration_s = 0.0
        if background_image_path:
            await websocket.send_json({
                "type": "progress", "stage": "assemble",
                "label": "Đang dựng video (ảnh nền + audio + phụ đề)",
                "stage_index": 3, "total_stages": len(STAGES),
            })
            from pipeline.video_renderer import render_video

            final_video_path = str(job_dir / "final.mp4")
            _video_start = time.monotonic()
            await asyncio.to_thread(
                render_video, final_audio_path, background_image_path,
                srt_path=final_srt_path, output_path=final_video_path,
                burn_subtitles=burn_subtitles,
            )
            video_duration_s = time.monotonic() - _video_start
            job["final_video_path"] = final_video_path

        qa_report = None
        qa_duration_s = 0.0
        if qa_enabled:
            await websocket.send_json({
                "type": "progress", "stage": "qa", "label": STAGES[4]["label"],
                "stage_index": 4, "total_stages": len(STAGES),
            })
            # Phase 4 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md, muc
            # 13 - verify_and_retry_chapter_quality() (orchestrator.py) tu
            # dong thu tong hop lai cac chunk bi gan co truoc khi bao cao,
            # thay vi chi bao "nghi ngo loi" roi cho nguoi dung tu render lai.
            from voxdirector.orchestrator import verify_and_retry_chapter_quality
            # QA tren TUNG chuong (verify_and_retry_chapter_quality yeu cau
            # chapter_dir rieng) - gop lai thanh 1 bao cao tong cho ca job.
            _qa_start = time.monotonic()
            all_flagged = []
            wers = []
            segments_retried_total = 0
            segments_fixed_total = 0
            any_chapter_changed = False
            # Muc 16 cua master plan (audio-health checks) - suc khoe song am
            # cua TUNG chuong (xem gamma_qa.verify_chapter_quality()), gop lai
            # thanh 1 tom tat cho CA JOB o duoi, cung cach voi wers/all_flagged.
            chapter_audio_health = []
            for ci, result in enumerate(chapter_results):
                chapter_dir = str(job_dir / f"chapter_{ci + 1}")
                r = await asyncio.to_thread(
                    verify_and_retry_chapter_quality, chapter_dir, f"chapter_{ci + 1}", result["chunks"],
                )
                wers.append(r["word_error_rate"])
                for f in r["flagged_segments"]:
                    f["chapter"] = ci + 1
                    all_flagged.append(f)
                chapter_audio_health.append(r.get("audio_health", {}))
                retry_summary = r["auto_retry_summary"]
                segments_retried_total += retry_summary["segments_retried"]
                segments_fixed_total += retry_summary["segments_fixed"]
                if retry_summary["segments_retried"] > 0:
                    any_chapter_changed = True
            qa_duration_s = time.monotonic() - _qa_start

            # rebuild_final_audio() da chay 1 lan TRUOC khoi QA nay (xem ben
            # tren) - neu retry vua ghi de {prefix}_merged.wav cua bat ky
            # chuong nao, final.wav cu se KHONG con phan anh dung audio da
            # sua, dung y het loi "nut Render lai khong hoat dong" ma chinh
            # assemble_final_audio() da tung fix mot lan (xem docstring ham
            # do) - phai goi lai o day. Dung rebuild_final_audio() (khong
            # phai assemble_final_audio() truc tiep) de BGM (neu co) duoc
            # tron LAI, khong bi mat sau khi QA sua audio.
            if any_chapter_changed:
                await asyncio.to_thread(
                    rebuild_final_audio, str(job_dir), len(chapter_results), sample_rate, final_audio_path,
                    job.get("background_music_path"), job.get("bgm_volume", 0.05),
                )

            qa_report = {
                "word_error_rate": round(sum(wers) / len(wers), 2) if wers else 0.0,
                "passed": all(w < 0.08 for w in wers) if wers else True,
                "flagged_segments_count": len(all_flagged),
                "flagged_segments": all_flagged,
                "auto_retry_summary": {
                    "segments_retried": segments_retried_total,
                    "segments_fixed": segments_fixed_total,
                },
                "audio_health": {
                    "any_clipping": any(h.get("clipping") for h in chapter_audio_health),
                    "any_near_silent": any(h.get("near_silent") for h in chapter_audio_health),
                    "total_internal_silence_gaps": sum(
                        len(h.get("long_silence_gaps", [])) for h in chapter_audio_health
                    ),
                },
            }
            # Section 5d cua PHASE0_HANDOFF.md - summarize_qa_report() da viet
            # san (voxdirector/agents/gamma_qa.py) nhung chua tung duoc goi;
            # tuy chon, tu fallback ve tom tat dung code neu khong co GEMINI_API_KEY
            # (xem docstring ham do) nen khong lam gian doan pipeline khi loi.
            from voxdirector.agents.gamma_qa import summarize_qa_report
            qa_report["summary"] = summarize_qa_report(qa_report)

        # Dedup theo term (khong phai extend tho) - xac nhan co THAT qua test
        # song 2026-09-13: cung 1 nhan vat duoc Beta flag lai o NHIEU chuong
        # (vd. "Lý Thiên Vũ" xuat hien ca chuong 1 lan chuong 2) tao 2 candidate
        # trung term o all_new_terms, khien React key={c.term} trong
        # NewTermConfirmationPanel dam vao nhau - nut "Duyệt" bao "Đang lưu..."
        # ket dinh du approve_new_entries() da chay dung o server (xac nhan qua
        # ChromaDB). Giu candidate XUAT HIEN DAU TIEN cho moi term la du -
        # nguoi dung chi can duyet 1 lan cho 1 ten rieng.
        all_new_terms = []
        seen_new_terms = set()
        all_expression_report = []
        all_pause_report = []
        for r in chapter_results:
            for candidate in r["new_entry_candidates"]:
                if candidate["term"] not in seen_new_terms:
                    seen_new_terms.add(candidate["term"])
                    all_new_terms.append(candidate)
            all_expression_report.extend(r["expression_report"])
            all_pause_report.extend(r["pause_report"])

        # Phase 3 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md, muc 12
        # ("diff view") - diff_ops la du lieu CAP CHUONG (khac new_term_candidates/
        # expression_report gop phang), giu nguyen 1 muc/chuong de frontend
        # render dung "Xem thay doi cua Beta (Chuong N)" cho tung chuong rieng.
        chapter_diffs = [
            {"chapter": ci + 1, "diff_ops": result["diff_ops"]}
            for ci, result in enumerate(chapter_results)
        ]

        segments = []
        seg_id = 1
        for ci, result in enumerate(chapter_results):
            for chunk_text in result["chunks"]:
                segments.append({
                    "id": seg_id,
                    "chapter": ci + 1,
                    "chunk_index_in_chapter": seg_id - 1,
                    "text": chunk_text,
                    "duration_s": None,
                    "flagged": any(
                        f.get("chapter") == ci + 1 and f.get("segment_index") == (seg_id - 1)
                        for f in (qa_report["flagged_segments"] if qa_report else [])
                    ),
                })
                seg_id += 1

        # 2026-09-13 (yeu cau nguoi dung: "266 tu -> audio 1:30 mat 2:15,
        # GPU co that su duoc dung khong?") - tach ro RANH GIOI tung giai
        # doan thay vi 1 con so tong duy nhat, de biet CHINH XAC thoi gian
        # di dau (Alpha/Beta la Gemini API, KHONG lien quan GPU cua may) thay
        # vi doan mo ho. beta_s/tts_s la TONG cong don tat ca chuong.
        timing_breakdown = {
            "alpha_s": job.get("alpha_duration_s", 0.0),
            "beta_s": round(sum(r.get("beta_duration_s", 0.0) for r in chapter_results), 1),
            "tts_s": round(sum(r.get("tts_duration_s", 0.0) for r in chapter_results), 1),
            "assemble_s": round(assemble_duration_s, 1),
            "video_s": round(video_duration_s, 1),
            "qa_s": round(qa_duration_s, 1),
        }

        processing_time_s = round(job.get("alpha_duration_s", 0.0) + (time.monotonic() - processing_started_at), 1)

        # Muc 18 cua master plan - doc TONG token Gemini cua CA job (Alpha +
        # moi chuong Beta/QA) 1 LAN duy nhat o day (truoc khi gui ket qua VA
        # truoc khi ghi DB ben duoi) - _pop_gemini_usage_summary() da XOA bo
        # dem sau khi doc, nen goi lai lan 2 se tra ve rong.
        gemini_usage = _pop_gemini_usage_summary(job_id)

        await websocket.send_json({
            "type": "result",
            "audio_url": f"/api/audio/{job_id}",
            "subtitle_url": f"/api/subtitles/{job_id}",
            "video_url": f"/api/video/{job_id}" if job.get("final_video_path") else None,
            "quality_summary": qa_report or {"word_error_rate": 0.0, "passed": True, "flagged_segments_count": 0},
            "segments": segments,
            "new_term_candidates": all_new_terms,
            "expression_report": all_expression_report,
            "pause_report": all_pause_report,
            "chapter_diffs": chapter_diffs,
            "processing_time_s": processing_time_s,
            "timing_breakdown": timing_breakdown,
            "gemini_usage": gemini_usage,
        })

        from voxdirector.db import record_job
        record_job(
            job_id=job_id,
            status="completed",
            num_chapters=len(alpha_result["chapters"]),
            detected_genre=alpha_result.get("detected_genre"),
            genre_confidence_score=alpha_result.get("genre_confidence_score"),
            chapters_needing_review=sum(1 for c in alpha_result["chapters"] if c.get("needs_review")),
            alpha_enabled=job.get("alpha_enabled", True),
            beta_enabled=beta_enabled,
            qa_enabled=qa_enabled,
            voice_id=voice_id,
            timing_breakdown=timing_breakdown,
            processing_time_s=processing_time_s,
            word_error_rate=(qa_report or {}).get("word_error_rate"),
            qa_passed=(qa_report or {}).get("passed") if qa_report else None,
            flagged_segments_count=(qa_report or {}).get("flagged_segments_count"),
            new_term_candidates_count=len(all_new_terms),
            gemini_prompt_tokens=gemini_usage["gemini_prompt_tokens"],
            gemini_output_tokens=gemini_usage["gemini_output_tokens"],
            estimated_cost_usd=gemini_usage["estimated_cost_usd"],
        )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        from voxdirector.db import record_job

        alpha_result_for_trace = job.get("alpha_result")
        gemini_usage = _pop_gemini_usage_summary(job_id)
        record_job(
            job_id=job_id,
            status="error",
            error_message=str(e),
            num_chapters=len(alpha_result_for_trace["chapters"]) if alpha_result_for_trace else None,
            alpha_enabled=job.get("alpha_enabled", True),
            beta_enabled=beta_enabled,
            qa_enabled=qa_enabled,
            voice_id=voice_id,
            gemini_prompt_tokens=gemini_usage["gemini_prompt_tokens"],
            gemini_output_tokens=gemini_usage["gemini_output_tokens"],
            estimated_cost_usd=gemini_usage["estimated_cost_usd"],
        )
        await websocket.send_json({"type": "error", "message": str(e)})


def _merge_subtitles(chapter_results, inter_chapter_gap_s, out_path):
    """Gop nhieu file .srt (moi chuong tu bat dau timestamp tu 0) thanh 1
    file .srt duy nhat, dich timestamp theo offset tich luy (tong do dai
    audio cac chuong truoc do + khoang lang giua chuong)."""
    import re
    import wave

    def parse_ts(ts):
        h, m, rest = ts.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    def format_ts(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def wav_duration(path):
        with wave.open(path, "rb") as w:
            return w.getnframes() / w.getframerate()

    entries = []
    offset = 0.0
    idx = 1
    for i, result in enumerate(chapter_results):
        srt_path = result.get("srt_path")
        if srt_path and os.path.isfile(srt_path):
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()
            blocks = [b for b in content.split("\n\n") if b.strip()]
            for block in blocks:
                lines = block.strip().split("\n")
                if len(lines) < 2:
                    continue
                ts_line = lines[1]
                m = re.match(r"(\S+) --> (\S+)", ts_line)
                if not m:
                    continue
                start = parse_ts(m.group(1)) + offset
                end = parse_ts(m.group(2)) + offset
                text = "\n".join(lines[2:])
                entries.append(f"{idx}\n{format_ts(start)} --> {format_ts(end)}\n{text}\n")
                idx += 1
        offset += wav_duration(result["merged_path"]) + inter_chapter_gap_s

    if not entries:
        return None
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(entries))
    return out_path


class RerenderRequest(BaseModel):
    job_id: str
    segment_id: int


@app.post("/api/rerender")
def rerender_segment(req: RerenderRequest):
    """Step 10 cua build order - "Segment re-render endpoint". segment_id la
    id lien tuc qua tat ca chuong (xem cach danh so trong ws_progress); tim
    dung chapter_dir + chunk_index tuong ung roi goi orchestrator.rerender_chunk().

    2026-09-12: sau khi rerender_chunk() cap nhat xong {prefix}_merged.wav
    cua DUNG chuong chua segment, PHAI goi lai rebuild_final_audio() de ghep
    lai final.wav cua CA JOB - neu khong, final.wav ma /api/audio/{job_id}
    phuc vu van la ban ghep CU, khong bao gio phan anh doan vua render lai
    (day CHINH LA loi "nut Render lai khong hoat dong" nguoi dung bao cao -
    xem docstring rebuild_final_audio() trong orchestrator.py). Dung
    rebuild_final_audio() (khong phai assemble_final_audio() truc tiep) de
    BGM (neu job co dung) duoc tron LAI thay vi bi mat sau moi lan render lai.

    LUU Y (gioi han con lai, chua fix): chi re-render lai audio, KHONG re-chay
    lai toan bo file .srt ghep (final.srt) - do dai chunk sau khi re-render co
    the doi nhe khien timestamp cac phan sau bi lech nho; ngoai pham vi
    "local end-to-end test" hien tai."""
    from fastapi import HTTPException
    from pipeline.vieneu_tts import get_sample_rate
    from voxdirector.orchestrator import rebuild_final_audio, rerender_chunk

    job = JOBS.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id không tồn tại")

    job_dir: Path = job["job_dir"]
    num_chapters = len(job["alpha_result"]["chapters"])
    seg_id = req.segment_id
    for ci in range(num_chapters):
        chapter_dir = job_dir / f"chapter_{ci + 1}"
        manifest_path = chapter_dir / f"chapter_{ci + 1}_manifest.json"
        if not manifest_path.is_file():
            continue
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        n_chunks = len(manifest["chunks"])
        if seg_id <= n_chunks:
            rerender_chunk(str(chapter_dir), seg_id - 1)
            if "final_audio_path" in job:
                sample_rate = manifest.get("sample_rate") or get_sample_rate(manifest["voice_id"])
                rebuild_final_audio(
                    str(job_dir), num_chapters, sample_rate, job["final_audio_path"],
                    job.get("background_music_path"), job.get("bgm_volume", 0.05),
                )
            return {"status": "ok", "chapter": ci + 1, "chunk_index": seg_id - 1}
        seg_id -= n_chunks

    raise HTTPException(status_code=404, detail="segment_id không tồn tại")
