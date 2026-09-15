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
- Export buttons: **"Xuất Audio"** (downloads the final `.wav`), **"Xuất
  Video"** (only enabled if you set a background image under "Tuỳ chọn nâng
  cao" before processing — video rendering needs that image as input, and
  the button greys out with a tooltip explaining why if you skip it),
  **"Xuất Phụ đề (.srt)"**.

## 6. New-term confirmation panel

If Beta encounters a proper noun / place / term not yet in the glossary, a
small dismissible panel appears in the bottom-right corner — on top of
whichever screen you're on, desktop or mobile — listing each candidate with
a **"Duyệt"** (approve) button. Approving writes the term straight into the
live Character/Terminology Glossary (ChromaDB) — it's picked up by Beta for
every chapter processed after that, in this job and future ones. You can
review, edit, or manually add/delete glossary entries any time from
**"Cài đặt dữ liệu" → Glossary → "Đang dùng (thời gian thực)"** (see
Settings below).

## 7. Settings ("Cài đặt dữ liệu", top-right)

Opens a small dialog listing the 3 data sections plus BYOK; each section's
**"Xem/Sửa"** (or **"Quản lý Glossary"**) button opens its own large,
dedicated dialog with a proper table editor — not a raw JSON textarea:

- **Từ điển cảm xúc** — flat table of (nhãn, từ/thẻ) rows. `emotion_label`
  determines what Alpha can flag; the word/tag is what Beta is allowed to
  insert. Currently ships with exactly 3 labels because that's the
  empirically-verified ceiling of what VieNeu-TTS actually honors as inline
  bracket tags (`[cười]`, `[thở dài]`, `[hắng giọng]`) — see the file's own
  `_note` for how that was tested.
- **Glossary** — its own tabbed dialog: **"Đang dùng (thời gian thực)"**
  (the live ChromaDB collection — same store the new-term panel's "Duyệt"
  writes to; full add/edit/delete here) and **"Khởi tạo"** (the static seed
  file loaded once at pipeline startup, independent of the live collection).
- **Bảng ngắt nghỉ theo dấu câu** — punctuation → short-pause-duration (ms)
  table for fine-grained in-chunk pausing.

All three editors share one toolbar per table (select-all checkbox, Add,
Delete-selected, Save) instead of a button per row — built for tables with
many entries, not just a handful.

A working **BYOK API key** field lets each person use their own Gemini key
instead of the server's shared one — stored in that browser's `localStorage`
only, sent once per `/api/submit` call, never persisted server-side beyond
the request being processed.

## Known gaps (by design, not bugs)

- Re-render (per-segment) doesn't recompute merged subtitle timing if the
  re-rendered chunk's length changes noticeably.
