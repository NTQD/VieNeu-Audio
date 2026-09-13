"""Step 9 cua build order (Section 11 cua spec) - noi that Alpha -> Beta ->
normalizer -> (sentinel-aware) splitter -> punctuation-pauses (Section 7.3,
da xac nhan can thiet qua Step 0 - CAN REVIEW LAI voi VieNeu-TTS, xem Step 5
cua yeu cau doi engine 2026-09-11, chua lam) -> TTS (VieNeu-TTS, xem
pipeline/vieneu_tts.py) -> (variable-silence) postprocess -> subtitle ->
Gamma QA (tuy chon).

2026-09-11: Piper da bi go bo hoan toan (dao nguoc quyet dinh dung Piper
2026-09-10, quay lai VieNeu-TTS). synthesize_to_file()/get_sample_rate() gio
import that tu pipeline/vieneu_tts.py (khong con la placeholder
NotImplementedError nua).

KHONG dung LangGraph (state.py cu tham chieu no nhung spec v5 hien tai
KHONG con nhac den LangGraph/graph.py o dau ca - xac nhan qua grep toan bo
VoxDirectorAI_Technical_Spec.md, 0 ket qua) - dung Python thuan de de test
tung buoc doc lap, giong toan bo phong cach code cua du an nay tu truoc gio.

MOT LUAT PROCESS DON GIAN CHO BAN LOCAL/1-MAY: dong bo, 1 tien trinh, khong
hang doi job rieng - phu hop pham vi "Step 14: local end-to-end test". San
xuat that (nhieu user dong thoi, VPS) se can hang doi/worker rieng, nhung do
la ngoai pham vi build order hien tai (Step 15 la deploy, khong phai scale)."""

import json
import os
import re
import time

from voxdirector.agents.alpha_ingestion import run_alpha
from voxdirector.agents.beta_consistency import run_beta
from voxdirector.config import DATA_DIR, PAUSE_LONG_TOKEN

_WHITESPACE_RE = re.compile(r"\s+")
# Fallback thuan regex khi nguoi dung TAT Agent Alpha (advanced options,
# 2026-09-12) - khong lien quan gi toi phan Alpha co the "tu tach chuong
# ngay ca khong co heading" (do la nang luc CUA Alpha, mat luon khi tat no).
# Chi bat dong "Chuong N"/"Chapter N" o DAU DONG - khong co gi tinh vi hon.
_CHAPTER_HEADING_RE = re.compile(r"^\s*(?:ch[uư][oơ]ng|chapter)\s+\d+\b.*$", re.IGNORECASE | re.MULTILINE)


def _normalize_ws(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def process_submission_fallback(raw_text: str) -> dict:
    """Duong di THAY THE khi nguoi dung tat Agent Alpha (advanced options,
    2026-09-12 - yeu cau "nut bat/tat tung Agent"). Dung REGEX DON GIAN de
    tach chuong (tim dong bat dau bang "Chuong N"/"Chapter N"), KHONG goi
    Gemini - nen KHONG co the loai, KHONG co goi y giong theo the loai, KHONG
    co cam xuc/diem ngat kich tinh duoc gan co (nhung nang luc do LA cua
    Alpha). Voice mac dinh (genre_to_voice["default"]) duoc dung, nguoi dung
    tu chon giong khac qua Advanced Options neu muon.

    Tra ve DUNG schema cua run_alpha() de process_chapter()/main.py khong can
    biet Alpha co thuc su chay hay khong - xem run_alpha() de doi chieu."""
    if not raw_text.strip():
        return {
            "chapters": [], "detected_genre": None, "suggested_voice_id": None,
            "genre_confidence_score": 0.0, "emotion_flagged_segments": [], "pause_points": [],
        }

    matches = list(_CHAPTER_HEADING_RE.finditer(raw_text))
    chapters = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        text = raw_text[start:end].strip()
        if text:
            chapters.append({
                "text": text, "start_index": start, "end_index": end,
                "confidence_score": 1.0, "needs_review": False,
            })
    if not chapters:
        chapters = [{
            "text": raw_text.strip(), "start_index": 0, "end_index": len(raw_text),
            "confidence_score": 1.0, "needs_review": False,
        }]

    from voxdirector.config import load_voice_presets
    default_voice = load_voice_presets()["genre_to_voice"]["default"]

    return {
        "chapters": chapters,
        "detected_genre": None,
        "suggested_voice_id": default_voice,
        "genre_confidence_score": 0.0,
        "emotion_flagged_segments": [],
        "pause_points": [],
    }


def _items_for_chapter(items: list[dict], chapter_text: str) -> list[dict]:
    """Loc emotion_flagged_segments/pause_points (tinh tren TOAN BO raw_text
    boi Alpha, chay 1 lan/submission - Section 6.1) ve dung nhung entry co
    quoted_text nam trong chapter_text NAY - Beta chi can flag cua dung
    chuong no dang xu ly (Section 6.2: "from Alpha, this same chapter")."""
    normalized_chapter = _normalize_ws(chapter_text)
    return [item for item in items if _normalize_ws(item["quoted_text"]) in normalized_chapter]


def process_submission(raw_text: str, api_key: str | None = None, alpha_enabled: bool = True) -> dict:
    """Section 3 step 2 cua spec: "Submit -> Alpha runs" - dong bo, chay 1
    lan cho toan bo van ban, TRUOC khi WebSocket progress cua Beta/TTS/QA bat
    dau. Tra ve nguyen schema cua run_alpha().

    api_key: BYOK - key rieng cua nguoi dung gui kem request (Section 13 cua
    spec, chot 2026-09-10: "users will use their own API key"). None thi
    dung key mac dinh cua server (voxdirector.config.GEMINI_API_KEY).

    alpha_enabled: nut bat/tat Agent Alpha (advanced options, 2026-09-12) -
    False dung process_submission_fallback() (regex thuan, khong goi Gemini)
    thay vi run_alpha()."""
    if not alpha_enabled:
        return process_submission_fallback(raw_text)
    return run_alpha(raw_text, api_key=api_key)


def process_chapter(
    chapter_text: str,
    chapter_emotion_segments: list[dict],
    chapter_pause_points: list[dict],
    chapter_dir: str,
    prefix: str,
    voice_id: str,
    pause_duration_ms_default: int = 500,
    qa_enabled: bool = False,
    beta_enabled: bool = True,
    chapter_number: int = 1,
    api_key: str | None = None,
) -> dict:
    """Xu ly 1 chuong day du: Beta -> normalizer -> splitter -> (Section 7.3
    neu can) -> TTS -> ghep -> subtitle -> QA (tuy chon). Ghi cac file .wav
    part vao chapter_dir voi ten "{prefix}_p{i:02d}.wav" (dung quy uoc voi
    gamma_qa.verify_chapter_quality()).

    Tra ve dict: {corrected_text, new_entry_candidates, chunks (list[str],
    dung cho subtitle/QA/re-render), boundary_flags, part_paths, merged_path,
    srt_path, qa_report (None neu qa_enabled=False)}.

    api_key: BYOK - key rieng cua nguoi dung, truyen xuong run_beta().

    beta_enabled: nut bat/tat Agent Beta (advanced options, 2026-09-12) -
    False bo qua hoan toan run_beta() (khong sua thuat ngu/glossary, khong
    chen tu bieu cam, khong chen sentinel [[PAUSE_LONG]]) - dung nguyen
    chapter_text goc lam corrected_text. Cung la 1 cach nguoi dung tu tranh
    truong hop chuong qua dai lam Beta cham gioi han max_output_tokens (xem
    voxdirector/llm_client.py) trong luc cho ban va cho ho fix triet de hon."""
    from pipeline.audio_postprocess import (
        concat_with_variable_silence,
        durations_from_boundary_flags,
        get_ffmpeg,
    )
    from pipeline.punctuation_pauses import split_chunk_by_punctuation
    from pipeline.subtitle_generator import generate_srt
    from pipeline.text_normalizer import normalize_text_for_tts
    from pipeline.text_splitter import split_text_with_boundaries
    from pipeline.vieneu_tts import get_sample_rate, synthesize_to_file

    os.makedirs(chapter_dir, exist_ok=True)
    ffmpeg = get_ffmpeg()
    # tts_duration_s bat dau tinh TU DAY (khong phai chi quanh vong lap
    # synthesize_to_file() ben duoi) - xac nhan co THAT qua do dac 2026-09-13:
    # get_sample_rate() la lan goi DAU TIEN cham vao pipeline.vieneu_tts._get_instance()
    # (singleton lazy-load) trong 1 chuong, nen tren request DAU TIEN sau khi
    # container khoi dong, no chinh la noi model VieNeu-TTS THAT SU duoc nap
    # vao bo nho (co the mat 10-40+ giay) - truoc ban sua nay, chi phi nay
    # KHONG duoc tinh vao dau ca (bi "mat tich" khoi timing_breakdown, khien
    # tong processing_time_s cao hon nhieu so voi tts_s hien thi, gay hieu
    # nham "GPU khong duoc dung" trong khi thuc ra la chi phi nap model 1 lan).
    _tts_start = time.monotonic()
    sample_rate = get_sample_rate(voice_id)
    tts_duration_s = time.monotonic() - _tts_start

    if beta_enabled:
        _beta_start = time.monotonic()
        beta_result = run_beta(
            chapter_text, chapter_emotion_segments, chapter_pause_points, chapter_number,
            api_key=api_key,
        )
        beta_duration_s = time.monotonic() - _beta_start
        corrected_text = beta_result["corrected_text"]

        # Xac nhan bang code, khong phai gia dinh (test standalone 2026-09-10):
        # Gemini doi khi tra ve corrected_text chua chuoi 2-ky-tu "\n" THAT (dau
        # gach cheo nguoc + chu n) thay vi ky tu xuong dong that - mot dang loi
        # dinh dang cua model, khong phai noi dung that. TTS se doc "n" nhu 1
        # ky tu roi rac giua cau neu khong sua - chuyen ve xuong dong that (giu
        # dung y nghia ngat doan) truoc khi dua vao normalizer/splitter/TTS.
        corrected_text = corrected_text.replace("\\n", "\n")
        applied_terms = beta_result["applied_terms"]
        new_entry_candidates = beta_result["new_entry_candidates"]
    else:
        # Beta tat - dung nguyen chapter_text goc, khong sua thuat ngu/chen
        # bieu cam/chen sentinel ngat dai (xem docstring tham so beta_enabled).
        corrected_text = chapter_text
        applied_terms = []
        new_entry_candidates = []
        beta_duration_s = 0.0

    normalized_text = normalize_text_for_tts(corrected_text)
    # Xac nhan bang code (khong gia dinh - Section 7.2 yeu cau kiem chung):
    # normalizer KHONG duoc lam mat sentinel truoc khi vao splitter.
    if PAUSE_LONG_TOKEN in corrected_text and PAUSE_LONG_TOKEN not in normalized_text:
        raise RuntimeError(
            f"text_normalizer.py da lam mat sentinel {PAUSE_LONG_TOKEN} - "
            "kiem tra lai cac quy tac normalize (Section 7.2 cua spec)."
        )

    chunks, boundary_flags = split_text_with_boundaries(normalized_text)
    chunk_silences = durations_from_boundary_flags(boundary_flags, pause_duration_ms_default / 1000.0)

    # Ghi text goc (da normalize) ra file de subtitle_generator doc lai -
    # dung quy uoc find_text_file() cua no ("{chapter_name}.txt" trong
    # chinh chapter_dir).
    text_path = os.path.join(chapter_dir, f"{os.path.basename(chapter_dir)}.txt")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(normalized_text)

    # tts_duration_s da khoi tao o tren (quanh get_sample_rate()) - cong don
    # tiep thoi gian tung synthesize_to_file() ben duoi vao CUNG 1 bien, tach
    # rieng voi thoi gian ffmpeg ghep manh (concat_with_variable_silence).
    part_paths = []
    for i, chunk_text in enumerate(chunks):
        # Section 7.3 (da xac nhan can thiet qua Step 0 cua build order):
        # tach nho hon theo dau cau BEN TRONG 1 chunk, tong hop tung manh,
        # roi tu ghep lai thanh audio hoan chinh cua chunk do - piece-level
        # concat_with_variable_silence(), KHAC voi chunk-level ben duoi.
        pieces, piece_pause_ms = split_chunk_by_punctuation(chunk_text)
        piece_paths = []
        for j, piece_text in enumerate(pieces):
            piece_path = os.path.join(chapter_dir, f"{prefix}_p{i + 1:02d}_piece{j:02d}.wav")
            _tts_start = time.monotonic()
            synthesize_to_file(piece_text, voice_id, piece_path)
            tts_duration_s += time.monotonic() - _tts_start
            piece_paths.append(piece_path)

        chunk_path = os.path.join(chapter_dir, f"{prefix}_p{i + 1:02d}.wav")
        if len(piece_paths) == 1:
            os.replace(piece_paths[0], chunk_path)
        else:
            piece_silences = [ms / 1000.0 for ms in piece_pause_ms]
            concat_with_variable_silence(ffmpeg, piece_paths, piece_silences, chunk_path, sample_rate=sample_rate)
            for p in piece_paths:
                os.remove(p)
        part_paths.append(chunk_path)

    merged_path = os.path.join(chapter_dir, f"{prefix}_merged.wav")
    if len(part_paths) == 1:
        import shutil
        shutil.copy(part_paths[0], merged_path)
    else:
        concat_with_variable_silence(ffmpeg, part_paths, chunk_silences, merged_path, sample_rate=sample_rate)

    srt_path = generate_srt(chapter_dir, text_file=text_path, boundary_silences=chunk_silences)

    # Manifest - de re-render 1 segment (Step 10) khong can chay lai
    # Alpha/Beta/normalizer/splitter, chi can doc lai chunks+boundary_flags
    # da luu.
    manifest_path = os.path.join(chapter_dir, f"{prefix}_manifest.json")
    manifest = {
        "prefix": prefix,
        "voice_id": voice_id,
        "chunks": chunks,
        "boundary_flags": boundary_flags,
        "pause_duration_ms_default": pause_duration_ms_default,
        "sample_rate": sample_rate,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    qa_report = None
    if qa_enabled:
        from voxdirector.agents.gamma_qa import verify_chapter_quality
        qa_report = verify_chapter_quality(chapter_dir, prefix, chunks)

    return {
        "corrected_text": corrected_text,
        "applied_terms": applied_terms,
        "new_entry_candidates": new_entry_candidates,
        "chunks": chunks,
        "boundary_flags": boundary_flags,
        "part_paths": part_paths,
        "merged_path": merged_path,
        "srt_path": srt_path,
        "manifest_path": manifest_path,
        "qa_report": qa_report,
        "beta_duration_s": beta_duration_s,
        "tts_duration_s": tts_duration_s,
    }


def assemble_final_audio(
    job_dir: str, num_chapters: int, sample_rate: int, final_audio_path: str,
    inter_chapter_gap_s: float = 1.0,
) -> str:
    """Ghep {prefix}_merged.wav cua TUNG chuong (chapter_1..chapter_N) thanh 1
    file final_audio_path DUY NHAT cho ca job - dung LAI o 2 noi: (1) lan dau
    sau khi xu ly xong tat ca chuong (backend/app/main.py:ws_progress), (2)
    sau khi re-render 1 segment (Step 10).

    QUAN TRONG (2026-09-12) - day CHINH LA fix cho loi "nut Render lai khong
    hoat dong" nguoi dung bao cao: rerender_chunk() ben duoi CHI cap nhat
    {prefix}_merged.wav cua DUNG 1 chuong chua segment do. Truoc ban sua nay,
    KHONG co gi goi lai buoc ghep noi cac chuong thanh final.wav sau do -
    final_audio_path ma /api/audio/{job_id} phuc vu cho trinh duyet la 1 ban
    COPY/GHEP DUOC TAO 1 LAN DUY NHAT truoc do, khong bao gio duoc ghi de -
    nen API tra ve 200 OK (rerender_chunk chay dung), nhung audio nguoi dung
    THUC SU nghe khong bao gio doi. Goi lai ham nay sau MOI lan rerender_chunk
    de final_audio_path luon phan anh dung cac file merged.wav moi nhat."""
    from pipeline.audio_postprocess import concat_with_variable_silence, get_ffmpeg

    merged_paths = [
        os.path.join(job_dir, f"chapter_{ci + 1}", f"chapter_{ci + 1}_merged.wav")
        for ci in range(num_chapters)
    ]
    if len(merged_paths) == 1:
        import shutil
        shutil.copy(merged_paths[0], final_audio_path)
    else:
        ffmpeg = get_ffmpeg()
        inter_chapter_silences = [inter_chapter_gap_s] * (len(merged_paths) - 1)
        concat_with_variable_silence(
            ffmpeg, merged_paths, inter_chapter_silences, final_audio_path, sample_rate=sample_rate,
        )
    return final_audio_path


def rerender_chunk(chapter_dir: str, chunk_index: int) -> str:
    """Section 11 Step 10 cua spec ("Segment re-render endpoint") - tong hop
    lai DUNG 1 chunk (segment) da chon tu manifest da luu, roi ghep lai
    toan bo chuong voi cac phan con lai giu nguyen (khong tong hop lai tu
    dau ca chuong). Tra ve merged_path da cap nhat."""
    from pipeline.audio_postprocess import concat_with_variable_silence, durations_from_boundary_flags, get_ffmpeg
    from pipeline.punctuation_pauses import split_chunk_by_punctuation
    from pipeline.vieneu_tts import synthesize_to_file

    manifest_candidates = [f for f in os.listdir(chapter_dir) if f.endswith("_manifest.json")]
    if not manifest_candidates:
        raise FileNotFoundError(f"Không tìm thấy manifest trong {chapter_dir}")
    manifest_path = os.path.join(chapter_dir, manifest_candidates[0])
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    prefix = manifest["prefix"]
    voice_id = manifest["voice_id"]
    chunks = manifest["chunks"]
    boundary_flags = manifest["boundary_flags"]
    sample_rate = manifest["sample_rate"]

    if not (0 <= chunk_index < len(chunks)):
        raise IndexError(f"chunk_index {chunk_index} ngoài phạm vi (0..{len(chunks) - 1})")

    ffmpeg = get_ffmpeg()
    chunk_text = chunks[chunk_index]
    pieces, piece_pause_ms = split_chunk_by_punctuation(chunk_text)
    piece_paths = []
    for j, piece_text in enumerate(pieces):
        piece_path = os.path.join(chapter_dir, f"{prefix}_p{chunk_index + 1:02d}_piece{j:02d}.wav")
        synthesize_to_file(piece_text, voice_id, piece_path)
        piece_paths.append(piece_path)

    chunk_path = os.path.join(chapter_dir, f"{prefix}_p{chunk_index + 1:02d}.wav")
    if len(piece_paths) == 1:
        os.replace(piece_paths[0], chunk_path)
    else:
        piece_silences = [ms / 1000.0 for ms in piece_pause_ms]
        concat_with_variable_silence(ffmpeg, piece_paths, piece_silences, chunk_path, sample_rate=sample_rate)
        for p in piece_paths:
            os.remove(p)

    part_paths = [os.path.join(chapter_dir, f"{prefix}_p{i + 1:02d}.wav") for i in range(len(chunks))]
    chunk_silences = durations_from_boundary_flags(
        boundary_flags, manifest["pause_duration_ms_default"] / 1000.0,
    )
    merged_path = os.path.join(chapter_dir, f"{prefix}_merged.wav")
    if len(part_paths) == 1:
        import shutil
        shutil.copy(part_paths[0], merged_path)
    else:
        concat_with_variable_silence(ffmpeg, part_paths, chunk_silences, merged_path, sample_rate=sample_rate)

    return merged_path
