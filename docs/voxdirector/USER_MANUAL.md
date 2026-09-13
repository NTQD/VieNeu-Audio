# VoxDirector AI — User Manual

The UI is in Vietnamese (target audience is a Vietnamese production team).
This manual is in English but quotes the exact on-screen labels so you can
match them directly.

## Layout

Two-column desktop layout (stacks into one column below ~768px width on
mobile — same flow either way, nothing is hidden or simplified on mobile).

- **Left column**: your input and options.
- **Right column**: always visible, shows an empty placeholder → live
  progress → final result, in place, without ever hiding the left column.

## 1. Submitting text

1. Either drag-and-drop a `.txt`/`.docx` file onto the dashed box, or paste
   text directly into the textarea below it ("...hoặc dán trực tiếp văn bản
   chương truyện vào đây.").
2. `.docx` parsing happens server-side once you submit — the drop zone
   accepts the file but doesn't preview `.docx` content client-side.

## 2. Genre & voice suggestion (appears automatically)

Once you click Start, Alpha (Gemini) analyzes the text and — before any
audio is generated — the left column shows:

- **"Thể loại phát hiện"** — detected genre badge (`kiem_hiep` / `ngon_tinh`
  / `trinh_tham`) with a confidence percentage.
- **"Giọng đọc đề xuất"** — a voice dropdown, pre-selected to Alpha's
  suggestion but freely editable before you continue. Options come from
  `data/voice_presets.json` via the backend, never hardcoded in the UI.
- **"N chương phát hiện được"** — chapter count.

## 3. Advanced options (collapsed by default — click "Tuỳ chọn nâng cao")

| Label | What it does | Default |
|---|---|---|
| Ảnh nền (tuỳ chọn) | Background image for video export | none |
| Nhạc nền (tuỳ chọn) | Background music to mix under the narration | none |
| Khoảng lặng mặc định giữa các phần | Default silence (ms) between ordinary chunk boundaries | 500ms |
| Ghi cứng phụ đề vào video | Burn subtitles into the exported video | on |
| Kiểm tra chất lượng (Agent Gamma — thử nghiệm) | Run ASR round-trip QA after synthesis (adds time — real faster-whisper transcription) | off |

Note: dramatic pause points that Alpha/Beta detect in the story (scene
breaks, tense silences) always get a *longer* pause than the slider value —
that's a separate, fixed setting (`PAUSE_LONG_DURATION_MS`, currently
1400ms) not exposed in this UI, distinct from the ordinary between-chunk gap
the slider controls.

## 4. Start processing

Click **"Bắt đầu xử lý"**. The right column switches to a progress view —
5 stages, each labeled, e.g. "Đang tạo giọng đọc (chương 1/2)". This step
calls Gemini (Beta) once per chapter and runs real TTS synthesis — expect
anywhere from ~10 seconds (short single-chapter text) to a minute or more
for longer, multi-chapter text, plus extra time if QA is enabled (it runs a
real speech-to-text pass).

## 5. Reviewing the result

- **"Bản xem trước"** — playable audio of the full result.
- **"Kiểm tra chất lượng (Gamma)"** panel (only shown if QA was enabled) —
  ĐẠT/CHƯA ĐẠT (passed/failed) badge plus measured Word Error Rate and how
  many segments got flagged as suspect.
- **"Danh sách đoạn"** — every chunk, in order, with:
  - a **"Nghi ngờ lỗi"** (suspected error) badge if QA flagged it,
  - its duration,
  - a **"Render lại"** (re-render) button — regenerates just that one
    chunk's audio in place and refreshes the player. Known limitation: this
    does not recompute the merged subtitle timestamps, so if the re-rendered
    chunk's length changes noticeably, later subtitle lines can drift
    slightly out of sync.
- Export buttons: **"Xuất Audio"** (works — downloads the final `.wav`),
  **"Xuất Video"** (intentionally disabled — video rendering isn't wired
  into the backend yet), **"Xuất Phụ đề (.srt)"** (works).

## 6. New-term confirmation panel

If Beta encounters a proper noun / place / term not yet in the glossary, a
small dismissible panel appears in the bottom-right corner — on top of
whichever screen you're on, desktop or mobile — listing each candidate with
a **"Duyệt"** (approve) button. Approving is currently a client-side
acknowledgement only; nothing is written back to the glossary automatically
yet (see Known Gaps below).

## 7. Settings ("Cài đặt dữ liệu", top-right)

Opens a dialog with three editable JSON files, each with a "Tải để sửa"
(load to edit) button, a raw JSON textarea, and "Lưu (ghi đè toàn bộ file)"
(save — replaces the whole file, not a merge):

- **Từ điển cảm xúc** — `emotion_label → [candidate words]`. Determines
  what Alpha can flag and what Beta is allowed to insert.
- **Glossary khởi tạo** — seed entries for the Character/Terminology
  Glossary (character names, places, terms and their canonical spelling).
- **Bảng ngắt nghỉ theo dấu câu** — punctuation → short-pause-duration (ms)
  table used for the fine-grained in-chunk pausing.

A disabled **BYOK API key** field is present but intentionally inert — the
spec leaves the safe-storage question for a personal Gemini key unresolved,
so nothing is saved or sent from that field yet.

## Known gaps (by design, not bugs)

- Video export is not wired — audio + subtitles are the verified path.
- "Duyệt" on a new-term candidate doesn't persist to the glossary yet.
- Re-render doesn't recompute merged subtitle timing.
- BYOK storage is a placeholder field only.
