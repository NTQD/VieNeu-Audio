"""Phase 1 cua docs/voxdirector/ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md
("Persistence & measurement") - SQLite job/trace log.

Ghi CHI SO tung agent moi job (confidence, needs_review, match/skip cua
Beta, WER cua Gamma, timing) - KHONG phai audio/text day du, cai do van o
JOBS (bo nho) + backend/app/_jobs/ (dia) nhu truoc, khong doi. Muc dich DUY
NHAT: song sot qua restart backend va tra loi duoc "cai nay co that su hoat
dong khong" bang so lieu tich luy qua nhieu job, thay vi cam giac "hinh nhu
on" chi tu 1 lan test thu cong.

Dung sqlite3 thuan cua Python (khong them dependency moi) - dung quy mo du
an nay (~3 nguoi dung beta, khong can Postgres/hang doi rieng). Moi ham ghi
(record_*) tu boc try/except va IN CANH BAO thay vi raise - 1 loi ghi trace
KHONG duoc phep lam gian doan pipeline that (cung nguyen tac voi
_seed_glossary_if_empty() trong backend/app/main.py).
"""

import os
import sqlite3
import threading
from datetime import datetime, timezone

from voxdirector.config import DB_PATH

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            num_chapters INTEGER,
            detected_genre TEXT,
            genre_confidence_score REAL,
            chapters_needing_review INTEGER,
            alpha_enabled INTEGER,
            beta_enabled INTEGER,
            qa_enabled INTEGER,
            voice_id TEXT,
            alpha_duration_s REAL,
            beta_duration_s REAL,
            tts_duration_s REAL,
            assemble_duration_s REAL,
            video_duration_s REAL,
            qa_duration_s REAL,
            processing_time_s REAL,
            word_error_rate REAL,
            qa_passed INTEGER,
            flagged_segments_count INTEGER,
            new_term_candidates_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(job_id),
            chapter_number INTEGER NOT NULL,
            alpha_confidence_score REAL,
            needs_review INTEGER,
            emotion_flagged_count INTEGER,
            pause_points_count INTEGER,
            applied_terms_count INTEGER,
            new_entry_candidates_count INTEGER,
            expression_matched_count INTEGER,
            expression_skipped_count INTEGER,
            pause_matched_count INTEGER,
            pause_skipped_count INTEGER,
            chunk_count INTEGER,
            beta_duration_s REAL,
            tts_duration_s REAL
        );
        CREATE INDEX IF NOT EXISTS idx_chapters_job_id ON chapters(job_id);
        CREATE TABLE IF NOT EXISTS eval_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            gemini_model TEXT,
            num_cases INTEGER,
            genre_accuracy REAL,
            chapter_count_accuracy REAL,
            emotion_recall REAL,
            pause_recall REAL,
            details_json TEXT
        );
        """
    )
    conn.commit()


def record_job(
    job_id: str,
    status: str,
    num_chapters: int | None = None,
    detected_genre: str | None = None,
    genre_confidence_score: float | None = None,
    chapters_needing_review: int | None = None,
    alpha_enabled: bool = True,
    beta_enabled: bool = True,
    qa_enabled: bool = False,
    voice_id: str | None = None,
    timing_breakdown: dict | None = None,
    processing_time_s: float | None = None,
    word_error_rate: float | None = None,
    qa_passed: bool | None = None,
    flagged_segments_count: int | None = None,
    new_term_candidates_count: int | None = None,
    error_message: str | None = None,
) -> None:
    """Ghi 1 dong tom tat cho 1 job da xu ly xong (thanh cong hoac loi) - goi
    1 lan luc ket thuc ws_progress(). INSERT OR REPLACE theo job_id, phong
    khi nao can ghi de (khong nen xay ra binh thuong, moi job_id la UUID
    moi)."""
    timing_breakdown = timing_breakdown or {}
    try:
        with _lock:
            conn = _get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO jobs (
                    job_id, created_at, status, error_message, num_chapters,
                    detected_genre, genre_confidence_score, chapters_needing_review,
                    alpha_enabled, beta_enabled, qa_enabled, voice_id,
                    alpha_duration_s, beta_duration_s, tts_duration_s,
                    assemble_duration_s, video_duration_s, qa_duration_s,
                    processing_time_s, word_error_rate, qa_passed,
                    flagged_segments_count, new_term_candidates_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    error_message,
                    num_chapters,
                    detected_genre,
                    genre_confidence_score,
                    chapters_needing_review,
                    int(alpha_enabled),
                    int(beta_enabled),
                    int(qa_enabled),
                    voice_id,
                    timing_breakdown.get("alpha_s"),
                    timing_breakdown.get("beta_s"),
                    timing_breakdown.get("tts_s"),
                    timing_breakdown.get("assemble_s"),
                    timing_breakdown.get("video_s"),
                    timing_breakdown.get("qa_s"),
                    processing_time_s,
                    word_error_rate,
                    None if qa_passed is None else int(qa_passed),
                    flagged_segments_count,
                    new_term_candidates_count,
                ),
            )
            conn.commit()
    except Exception as e:
        print(f"[VoxDirector] Canh bao: khong ghi duoc job trace vao DB ({e}) - khong anh huong pipeline.")


def record_chapter(
    job_id: str,
    chapter_number: int,
    alpha_confidence_score: float | None,
    needs_review: bool,
    emotion_flagged_count: int,
    pause_points_count: int,
    applied_terms_count: int,
    new_entry_candidates_count: int,
    expression_report: list[dict],
    pause_report: list[dict],
    chunk_count: int,
    beta_duration_s: float,
    tts_duration_s: float,
) -> None:
    """Ghi 1 dong trace cho 1 chuong da xu ly xong - goi ngay sau moi
    process_chapter() thanh cong trong vong lap cua ws_progress()."""
    expression_matched = sum(1 for e in expression_report if e.get("matched"))
    pause_matched = sum(1 for p in pause_report if p.get("matched"))
    try:
        with _lock:
            conn = _get_conn()
            conn.execute(
                """INSERT INTO chapters (
                    job_id, chapter_number, alpha_confidence_score, needs_review,
                    emotion_flagged_count, pause_points_count, applied_terms_count,
                    new_entry_candidates_count, expression_matched_count,
                    expression_skipped_count, pause_matched_count, pause_skipped_count,
                    chunk_count, beta_duration_s, tts_duration_s
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    chapter_number,
                    alpha_confidence_score,
                    int(needs_review),
                    emotion_flagged_count,
                    pause_points_count,
                    applied_terms_count,
                    new_entry_candidates_count,
                    expression_matched,
                    len(expression_report) - expression_matched,
                    pause_matched,
                    len(pause_report) - pause_matched,
                    chunk_count,
                    beta_duration_s,
                    tts_duration_s,
                ),
            )
            conn.commit()
    except Exception as e:
        print(f"[VoxDirector] Canh bao: khong ghi duoc chapter trace vao DB ({e}) - khong anh huong pipeline.")


def record_eval_run(
    gemini_model: str,
    num_cases: int,
    genre_accuracy: float | None,
    chapter_count_accuracy: float | None,
    emotion_recall: float | None,
    pause_recall: float | None,
    details_json: str,
) -> None:
    """Ghi 1 lan chay scripts/run_eval.py - lich su qua thoi gian de so sanh
    truoc/sau khi doi prompt Agent (Section "Phase 1" muc 6 cua master
    plan)."""
    try:
        with _lock:
            conn = _get_conn()
            conn.execute(
                """INSERT INTO eval_runs (
                    run_at, gemini_model, num_cases, genre_accuracy,
                    chapter_count_accuracy, emotion_recall, pause_recall, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    gemini_model,
                    num_cases,
                    genre_accuracy,
                    chapter_count_accuracy,
                    emotion_recall,
                    pause_recall,
                    details_json,
                ),
            )
            conn.commit()
    except Exception as e:
        print(f"[VoxDirector] Canh bao: khong ghi duoc eval run vao DB ({e}).")


def job_stats() -> dict:
    """Thong ke tong hop nhanh tren toan bo job da ghi - dung cho CLI/kiem
    tra thu cong, khong dung trong pipeline chinh."""
    conn = _get_conn()
    total, avg_time, avg_wer = conn.execute(
        "SELECT COUNT(*), AVG(processing_time_s), AVG(word_error_rate) FROM jobs WHERE status='completed'"
    ).fetchone()
    total_chapters, total_needs_review = conn.execute(
        "SELECT COUNT(*), SUM(needs_review) FROM chapters"
    ).fetchone()
    return {
        "total_jobs": total or 0,
        "avg_processing_time_s": avg_time,
        "avg_word_error_rate": avg_wer,
        "total_chapters": total_chapters or 0,
        "chapters_needing_review": total_needs_review or 0,
    }
