"""Build order Step 4 (Section 11 cua spec) - test standalone Agent Alpha
v5 tren van ban mau bao phu CA 4 trach nhiem: (1) chuong, (2) the loai/giong,
(3) gan co cam xuc, (4) gan co diem can ngat kich tinh dai. Goi Gemini THAT
(khong mock) - can GEMINI_API_KEY trong bien moi truong.

Chay: python scratch_check/test_alpha_v5.py
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Van ban mau: 2 chuong ro rang (heading "Chuong 1"/"Chuong 2"), tin hieu the
# loai kiem hiep (kiem, giang ho, mon phai), 1 doan cam xuc ro rang (cuoi -
# loi thoai truc tiep "cuoi lon"), 1 diem chuyen canh/im lang ro rang cuoi
# chuong 1 (ung vien pause point).
SAMPLE_TEXT = """Chương 1: Hắc Vân Môn

Lý Phong dừng bước trước cổng Hắc Vân Môn, tay nắm chặt thanh kiếm bên hông.
Gã đã lang bạt giang hồ nhiều năm, chưa từng thấy môn phái nào u ám như thế
này.

- Ha ha ha! Ngươi tưởng một mình có thể phá được trận pháp của bổn môn sao?

Tiếng cười lớn vang vọng khắp đại sảnh, đầy vẻ ngạo mạn và khinh thường.

Đêm đó, cả tòa sơn trang chìm vào im lặng tuyệt đối, chỉ còn tiếng gió rít
qua từng khe đá, như thể đang chờ đợi một điều gì đó sắp xảy ra.

Chương 2: Trận Chiến Sau Cổng

Sáng hôm sau, Lý Phong một mình xông vào trận pháp, kiếm khí ngập trời.
"""


def main():
    from voxdirector.agents.alpha_ingestion import run_alpha

    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print("LOI: chua co GEMINI_API_KEY/GOOGLE_API_KEY trong bien moi truong.")
        sys.exit(1)

    print(f"Do dai van ban mau: {len(SAMPLE_TEXT)} ky tu, {len(SAMPLE_TEXT.split())} tu\n")
    print("Dang goi Agent Alpha (Gemini that)...\n")

    result = run_alpha(SAMPLE_TEXT)

    print("=== (1) CHAPTERS ===")
    for i, c in enumerate(result["chapters"]):
        print(f"  [{i}] conf={c['confidence_score']:.2f} needs_review={c['needs_review']} "
              f"text[:40]={c['text'][:40]!r}...")

    print("\n=== (2) GENRE + VOICE ===")
    print(f"  detected_genre: {result['detected_genre']}")
    print(f"  genre_confidence_score: {result['genre_confidence_score']:.2f}")
    print(f"  suggested_voice_id: {result['suggested_voice_id']}")

    print("\n=== (3) EMOTION FLAGGED SEGMENTS ===")
    if not result["emotion_flagged_segments"]:
        print("  (rong - Alpha khong tim thay doan cam xuc nao du du lieu mau co)")
    for s in result["emotion_flagged_segments"]:
        print(f"  label={s['emotion_label']} conf={s['confidence_score']:.2f} "
              f"quoted_text={s['quoted_text']!r}")

    print("\n=== (4) PAUSE POINTS ===")
    if not result["pause_points"]:
        print("  (rong - Alpha khong tim thay diem ngat nao du du lieu mau co)")
    for p in result["pause_points"]:
        print(f"  conf={p['confidence_score']:.2f} reason={p['reason']!r} "
              f"quoted_text={p['quoted_text']!r}")

    print("\n=== KIEM TRA CO BAN (khong thay the doc ket qua that o tren) ===")
    checks = [
        ("co it nhat 2 chuong", len(result["chapters"]) >= 2),
        ("detected_genre hop le (kiem_hiep/ngon_tinh/trinh_tham)", result["detected_genre"] in ("kiem_hiep", "ngon_tinh", "trinh_tham")),
        ("suggested_voice_id khong rong", bool(result["suggested_voice_id"])),
    ]
    for label, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {label}")


if __name__ == "__main__":
    main()
