"""Step 14 cua build order - "Local end-to-end test, including at least one
sample with a genuine pause point and one with a genuine emotion segment" -
goi truc tiep API that (khong qua browser, tranh cac van de gian tiep cua
cong cu automation trinh duyet) de co 1 lan chay sach, xac dinh, dung de do
dac khach quan (khoang lang, WER) va gui file cho nguoi dung tu nghe that.

Yeu cau backend that dang chay tai localhost:8000 (khong phai stub).

Chay: python scratch_check/test_e2e_real.py
"""
import asyncio
import json
import os
import sys
import wave

import httpx
import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

SAMPLE_TEXT = """Chương 1: Hắc Vân Môn

Lý Phong dừng bước trước cổng Hắc Vân Môn, tay nắm chặt thanh kiếm bên hông. Gã đã lang bạt giang hồ nhiều năm, chưa từng thấy môn phái nào u ám như thế này.

- Ha ha ha! Ngươi tưởng một mình có thể phá được trận pháp của bổn môn sao?

Tiếng cười lớn vang vọng khắp đại sảnh, đầy vẻ ngạo mạn và khinh thường.

Đêm đó, cả tòa sơn trang chìm vào im lặng tuyệt đối, chỉ còn tiếng gió rít qua từng khe đá, như thể đang chờ đợi một điều gì đó sắp xảy ra."""


def wav_duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


async def main():
    print(f"Van ban mau: {len(SAMPLE_TEXT.split())} tu\n")

    print("1) POST /api/submit (Alpha that)...")
    r = httpx.post(f"{BASE_URL}/api/submit", json={"text": SAMPLE_TEXT}, timeout=60)
    r.raise_for_status()
    submit_result = r.json()
    print(f"   job_id={submit_result['job_id']}")
    print(f"   detected_genre={submit_result['detected_genre']} ({submit_result['genre_confidence_score']:.0%})")
    print(f"   suggested_voice_id={submit_result['suggested_voice_id']}")
    print(f"   chapters={submit_result['chapters']}\n")

    job_id = submit_result["job_id"]
    voice_id = submit_result["suggested_voice_id"]

    print("2) WS /api/ws (Beta + TTS + postprocess + QA that)...")
    ws_url = f"{WS_URL}/api/ws/{job_id}?voice_id={voice_id}&pause_duration_ms=500&qa_enabled=true"
    result = None
    async with websockets.connect(ws_url, open_timeout=10) as ws:
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "progress":
                print(f"   [{msg['stage_index']+1}/{msg['total_stages']}] {msg['label']}")
            elif msg["type"] == "result":
                result = msg
                break
            elif msg["type"] == "error":
                print(f"   LOI: {msg['message']}")
                return

    if result is None:
        print("KHONG nhan duoc ket qua cuoi cung.")
        return

    print("\n=== KET QUA ===")
    print(f"audio_url: {result['audio_url']}")
    print(f"subtitle_url: {result['subtitle_url']}")
    print(f"quality_summary: {result['quality_summary']}")
    print(f"so segment: {len(result['segments'])}")
    for s in result["segments"]:
        print(f"  - id={s['id']} chuong={s['chapter']} flagged={s['flagged']} text[:50]={s['text'][:50]!r}")
    print(f"new_term_candidates: {result['new_term_candidates']}")

    # Tai audio that ve local de gui cho nguoi dung nghe.
    audio_resp = httpx.get(f"{BASE_URL}{result['audio_url']}", timeout=30)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "e2e_real_final.wav")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(audio_resp.content)
    print(f"\nDa tai audio ve: {out_path} ({wav_duration(out_path):.2f}s)")

    srt_resp = httpx.get(f"{BASE_URL}{result['subtitle_url']}", timeout=30)
    srt_path = out_path.replace(".wav", ".srt")
    with open(srt_path, "wb") as f:
        f.write(srt_resp.content)
    print(f"Da tai subtitle ve: {srt_path}")

    # Kiem tra khach quan: doc manifest cua chuong de xem boundary_flags that.
    job_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backend", "app", "_jobs", job_id, "chapter_1",
    )
    manifest_path = os.path.join(job_dir, "chapter_1_manifest.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        print(f"\n=== MANIFEST CHUONG 1 ===")
        print(f"so chunk: {len(manifest['chunks'])}")
        print(f"boundary_flags: {manifest['boundary_flags']}")
        has_pause_long = "pause_long" in manifest["boundary_flags"]
        print(f"[{'OK' if has_pause_long else 'FAIL'}] co it nhat 1 ranh gioi pause_long (sentinel duoc chen + tach chunk)")

        if has_pause_long:
            # Do khoang lang THAT tai ranh gioi pause_long trong merged.wav.
            part_files = sorted(
                f for f in os.listdir(job_dir)
                if f.startswith("chapter_1_p") and f.endswith(".wav")
            )
            part_paths = [os.path.join(job_dir, f) for f in part_files]
            merged_path = os.path.join(job_dir, "chapter_1_merged.wav")
            sum_parts = sum(wav_duration(p) for p in part_paths)
            merged_dur = wav_duration(merged_path)
            print(f"tong do dai parts (khong lang): {sum_parts:.3f}s")
            print(f"do dai merged.wav: {merged_dur:.3f}s")
            print(f"=> khoang lang do duoc: {merged_dur - sum_parts:.3f}s (mong doi ~1.4s cho pause_long)")


if __name__ == "__main__":
    asyncio.run(main())
