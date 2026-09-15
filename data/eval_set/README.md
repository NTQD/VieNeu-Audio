# Alpha eval set (Phase 1, mục 6 của docs/voxdirector/handoffs/ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md)

Mục đích: trả lời "Agent Alpha thực sự tách chương/nhận diện thể loại/gắn cờ
cảm xúc-ngắt nghỉ tốt đến đâu" bằng **số đo được**, thay vì "hình như ổn" từ
vài lần test thủ công. Chạy lại bộ này sau **mỗi lần đổi prompt** của Alpha
(`voxdirector/agents/alpha_ingestion.py`) để biết thay đổi đó làm tốt hơn
hay tệ hơn.

**Phạm vi hiện tại: chỉ Alpha.** Đánh giá Beta/Gamma cần audio/TTS thật (tốn
kém hơn nhiều) — để dành cho Phase 2-4 của master plan khi cần.

## `cases.json` hiện đang RỖNG — đây là việc cần làm, không phải lỗi

File `cases.json` bắt đầu với `"cases": []`. Đây là chủ đích: dự án này có
nguyên tắc xuyên suốt "không bịa dữ liệu" (xem `docs/voxdirector/handoffs/PHASE0_HANDOFF.md`, mục 6) —
một "bộ eval" với ranh giới chương/nhãn cảm xúc do AI tự đoán rồi giả vờ là
đã được con người xác nhận sẽ **tệ hơn** không có eval set nào cả (đo lường
sai một cách tự tin). Vì vậy Claude sẽ không tự điền case thật vào đây —
việc đó cần **bạn** cung cấp chương thật + xác nhận đúng/sai của bạn.

Cách thêm 1 case thật (mất khoảng 5-10 phút/case):
1. Lấy 1 đoạn văn bản thật (1 chương hoặc vài đoạn, khoảng 300-1500 từ) từ
   thể loại bạn quan tâm (kiếm hiệp/ngôn tình/trinh thám/khác).
2. Tự đọc và xác định: nó nên được tách thành mấy chương? Thể loại gì? Đoạn
   nào thực sự có cảm xúc rõ (trích nguyên văn câu đó)? Đoạn nào thực sự nên
   có khoảng ngắt kịch tính dài?
3. Thêm 1 object vào mảng `cases` theo đúng schema bên dưới.
4. Chạy `python scripts/run_eval.py` để xem Alpha khớp ký vọng của bạn đến
   đâu.

Chỉ cần 5-10 case ban đầu (không cần đủ 10-20 ngay) đã cho tín hiệu hữu ích
hơn 0 case rất nhiều — có thể bổ sung dần.

## Schema 1 case (ví dụ minh hoạ — KHÔNG có trong `cases.json` thật, chỉ để
biết đúng hình dạng field)

```json
{
  "id": "case_001",
  "text": "Chương 1\n\n<toàn bộ văn bản thật của bạn ở đây>...",
  "expected_genre": "kiem_hiep",
  "expected_chapter_count": 2,
  "expected_emotion_segments": [
    {"quoted_text": "<trích nguyên văn CHÍNH XÁC từ text ở trên>", "emotion_label": "cười"}
  ],
  "expected_pause_points": [
    {"quoted_text": "<trích nguyên văn CHÍNH XÁC từ text ở trên>"}
  ]
}
```

Ghi chú field:
- `id`: bất kỳ chuỗi duy nhất nào, dùng để đọc report.
- `text`: **bắt buộc**, toàn bộ input sẽ đưa thẳng vào `run_alpha()`.
- `expected_genre`/`expected_chapter_count`/`expected_emotion_segments`/
  `expected_pause_points`: đều **tùy chọn** — bỏ trống field nào bạn chưa
  chắc chắn, `scripts/run_eval.py` chỉ tính chỉ số cho field bạn có cung
  cấp (không phạt điểm 0% cho field bạn không đánh giá).
- `quoted_text` phải là **trích dẫn nguyên văn** xuất hiện trong `text` —
  công thức so khớp trong `run_eval.py` dùng substring sau khi chuẩn hoá
  khoảng trắng, không fuzzy-match ngữ nghĩa.
- `emotion_label` phải là đúng **key thô** trong `data/emotion_lexicon.json`
  (vd. `"cuoi"`, `"tho_dai"`, `"hang_giong"` — không dấu), **KHÔNG phải**
  bracket tag ở value (`"[cười]"`/`"cười"`) — đây là lỗi dễ mắc đã gặp thật
  khi tự kiểm thử harness này: dùng nhầm `"cười"` khiến `emotion_recall`
  báo 0% dù Alpha đã gắn cờ đúng đoạn văn, chỉ vì so sai nhãn.

## Chạy eval

```bash
python scripts/run_eval.py
```

In ra kết quả từng case + số liệu tổng hợp (genre_accuracy,
chapter_count_accuracy, emotion_recall, pause_recall), đồng thời ghi 1 dòng
lịch sử vào bảng `eval_runs` của SQLite job trace log
(`voxdirector/db.py`) — để so sánh qua các lần chạy sau khi đổi prompt.

Dùng `--cases path/khac.json` nếu muốn chạy 1 bộ case khác (vd. eval set
riêng cho từng thể loại).
