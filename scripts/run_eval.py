"""Phase 1 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Persistence &
measurement", muc 6) - chay Agent Alpha tren bo eval case THAT (do con nguoi
cham diem, xem data/eval_set/README.md) va tinh chi so khop voi ky vong, de
tra loi "Alpha thuc su tach chuong/nhan dien the loai/gan co cam xuc-ngat
nghi tot den dau" bang so do duoc, thay vi cam giac "hinh nhu on".

Pham vi hien tai: CHI Agent Alpha (khong can TTS/audio, re va nhanh de chay
lai sau moi lan doi prompt). Danh gia Beta/Gamma can audio that, ton kem hon
nhieu - de danh cho Phase 2-4 cua master plan.

Chay: python scripts/run_eval.py [--cases path/to/cases.json]
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voxdirector.agents.alpha_ingestion import run_alpha
from voxdirector.config import GEMINI_MODEL
from voxdirector.db import record_eval_run

DEFAULT_CASES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "eval_set", "cases.json"
)

_WS_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", text).strip().lower()


def _recall(expected_items: list[dict], actual_items: list[dict], label_key: str | None = None):
    """Ty le expected_items duoc tim thay trong actual_items - so khop
    substring CHINH XAC (sau khi chuan hoa khoang trang/hoa-thuong), khong
    fuzzy-match ngu nghia (tranh bao khop nham). Tra ve None (khong ap dung)
    neu case nay khong khai bao expected_items nao cho muc nay - phan biet
    "khong danh gia" voi "danh gia va sai 100%"."""
    if not expected_items:
        return None
    matched = 0
    for exp in expected_items:
        exp_text = _norm(exp["quoted_text"])
        for act in actual_items:
            if exp_text not in _norm(act["quoted_text"]):
                continue
            if label_key and exp.get(label_key) != act.get(label_key):
                continue
            matched += 1
            break
    return matched / len(expected_items)


def evaluate_case(case: dict) -> dict:
    result = run_alpha(case["text"])

    genre_match = None
    if case.get("expected_genre") is not None:
        genre_match = result["detected_genre"] == case["expected_genre"]

    chapter_count_match = None
    if case.get("expected_chapter_count") is not None:
        chapter_count_match = len(result["chapters"]) == case["expected_chapter_count"]

    emotion_recall = _recall(
        case.get("expected_emotion_segments", []), result["emotion_flagged_segments"], "emotion_label",
    )
    pause_recall = _recall(case.get("expected_pause_points", []), result["pause_points"])

    return {
        "case_id": case["id"],
        "genre_match": genre_match,
        "detected_genre": result["detected_genre"],
        "chapter_count_match": chapter_count_match,
        "actual_chapter_count": len(result["chapters"]),
        "emotion_recall": emotion_recall,
        "pause_recall": pause_recall,
    }


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=DEFAULT_CASES_PATH)
    args = parser.parse_args()

    with open(args.cases, "r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", [])

    if not cases:
        print(
            f"[run_eval] {args.cases} chua co case nao. Xem data/eval_set/README.md de "
            f"biet cach them case that - KHONG bia du lieu (nguyen tac cua du an, xem "
            f"docs/voxdirector/PHASE0_HANDOFF.md muc 6)."
        )
        return

    per_case = []
    for case in cases:
        print(f"[run_eval] Dang chay case {case['id']!r}...")
        per_case.append(evaluate_case(case))

    genre_accuracy = _avg([1.0 if r["genre_match"] else 0.0 for r in per_case if r["genre_match"] is not None])
    chapter_count_accuracy = _avg(
        [1.0 if r["chapter_count_match"] else 0.0 for r in per_case if r["chapter_count_match"] is not None]
    )
    emotion_recall = _avg([r["emotion_recall"] for r in per_case])
    pause_recall = _avg([r["pause_recall"] for r in per_case])

    print("\n=== Ket qua eval Agent Alpha ===")
    for r in per_case:
        print(
            f"  {r['case_id']}: genre_match={r['genre_match']} "
            f"(detected={r['detected_genre']!r}) "
            f"chapter_count_match={r['chapter_count_match']} "
            f"(actual={r['actual_chapter_count']}) "
            f"emotion_recall={r['emotion_recall']} pause_recall={r['pause_recall']}"
        )
    print(f"\nTong hop ({len(per_case)} case, model={GEMINI_MODEL}):")
    print(f"  genre_accuracy: {genre_accuracy}")
    print(f"  chapter_count_accuracy: {chapter_count_accuracy}")
    print(f"  emotion_recall: {emotion_recall}")
    print(f"  pause_recall: {pause_recall}")

    record_eval_run(
        gemini_model=GEMINI_MODEL,
        num_cases=len(per_case),
        genre_accuracy=genre_accuracy,
        chapter_count_accuracy=chapter_count_accuracy,
        emotion_recall=emotion_recall,
        pause_recall=pause_recall,
        details_json=json.dumps(per_case, ensure_ascii=False),
    )
    print("\n[run_eval] Da ghi ket qua vao SQLite job trace log (bang eval_runs).")


if __name__ == "__main__":
    main()
