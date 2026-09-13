# VoxDirector AI — Manual Test Checklist

Run through these against either the Docker stack (`http://localhost`) or
local dev (`http://localhost:3000`). Gemini's free tier caps at 20
requests/day/model — Alpha uses 1 per submission, Beta uses 1 per chapter,
so budget accordingly (a 3-chapter run costs 4 requests).

Suggested sample text (has one clear emotion cue and one clear pause point —
useful for sections 3 and 5 below):

```
Chương 1: Hắc Vân Môn

Lý Phong dừng bước trước cổng Hắc Vân Môn, tay nắm chặt thanh kiếm bên hông.

- Ha ha ha! Ngươi tưởng một mình có thể phá được trận pháp của bổn môn sao?

Tiếng cười lớn vang vọng khắp đại sảnh, đầy vẻ ngạo mạn và khinh thường.

Đêm đó, cả tòa sơn trang chìm vào im lặng tuyệt đối, chỉ còn tiếng gió rít
qua từng khe đá, như thể đang chờ đợi một điều gì đó sắp xảy ra.
```

---

## 1. Layout & responsiveness

- [ ] Desktop width (≥1024px): left and right columns render side by side,
      right column visible (empty state) even before submitting anything.
- [ ] Resize the browser window down through ~768px: layout stacks to a
      single column — left column content first, right column below.
      **Actually resize the window** rather than assuming — this session's
      earlier work confirmed both states but the collapsible interaction at
      the breakpoint transition was never manually clicked through.
- [ ] Mobile width (375px): same functional flow, nothing hidden or cut off,
      no horizontal scroll.

## 2. Text input

- [ ] Paste text directly into the textarea — appears correctly, including
      Vietnamese diacritics (this session hit a real bug where retyping via
      browser automation silently duplicated/garbled text — worth a plain
      manual paste check).
- [ ] Drag a `.txt` file onto the dashed drop zone — content loads into the
      textarea.
- [ ] Drag a `.docx` file — zone accepts it (parsing happens server-side on
      submit, not previewed client-side).
- [ ] "Bắt đầu xử lý" is disabled while the textarea is empty, enabled once
      there's text.

## 3. Submit → Alpha suggestion

- [ ] Click "Bắt đầu xử lý" with the sample text above.
- [ ] Within a few seconds (before any audio starts), left column shows:
  - [ ] "Thể loại phát hiện" badge = `kiem_hiep` with a confidence %.
  - [ ] "Giọng đọc đề xuất" dropdown pre-filled, and **you can change it**
        before processing continues.
  - [ ] Chapter count line.
- [ ] Change the voice dropdown to a different option, confirm the final
      audio actually uses the new voice (audibly different, not just UI).

## 4. Advanced options

- [ ] Collapsible starts closed; clicking "Tuỳ chọn nâng cao" opens it.
- [ ] Pause-duration slider moves and shows the current ms value live.
- [ ] "Ghi cứng phụ đề vào video" and "Kiểm tra chất lượng (Agent Gamma)"
      toggles switch on/off visibly.
- [ ] Set the pause slider to a **low** value (e.g. 200ms) and a **high**
      value (e.g. 800ms) in two separate runs of the same text — confirm the
      ordinary (non-dramatic) inter-chunk silence is audibly different
      between the two exports.

## 5. Processing & the pause/emotion mechanism

- [ ] Enable "Kiểm tra chất lượng (Agent Gamma)" before starting.
- [ ] Progress stages appear in order (5 steps) with chapter-numbered labels
      once past the first stage.
- [ ] After completion, listen to the result:
  - [ ] The laughing line ("Ha ha ha!...") has an audible expressive word
        inserted near it (Beta may vary which line gets it, and doesn't
        always succeed — treat this as probabilistic, not guaranteed every
        run).
  - [ ] The line describing the silence at the end has a **noticeably
        longer** pause after it than the ordinary pauses elsewhere in the
        same clip. This doesn't fire every run either — Beta sometimes
        skips inserting the pause sentinel; if it's missing, check whether
        the QA/segment list still looks otherwise correct and try again.
- [ ] QA panel appears with a WER% and ĐẠT/CHƯA ĐẠT badge — the panel
      working correctly is what's under test here, not voice quality itself.

## 6. Result view

- [ ] Audio player loads and plays.
- [ ] "Danh sách đoạn" lists one row per chunk with correct text preview.
- [ ] If QA was enabled and flagged a segment, it shows the "Nghi ngờ lỗi"
      badge.
- [ ] "Xuất Audio" downloads a playable `.wav`.
- [ ] "Xuất Phụ đề (.srt)" downloads a valid `.srt` (open it — timestamps
      should roughly track the audio, especially across a chapter boundary
      if you test multi-chapter text).
- [ ] "Xuất Video" is disabled (expected — not a bug).

## 7. Re-render

- [ ] Click "Render lại" on one segment.
- [ ] Button shows a loading state, then the audio player refreshes with
      the updated take (listen for an actual change, or at minimum confirm
      no error and the player still plays start to finish).
- [ ] Known limitation to confirm, not fix: if the re-rendered chunk's
      duration changed noticeably, check whether later `.srt` timestamps
      drifted — this is expected, not a regression.

## 8. New-term panel

- [ ] After a run where Beta finds an unrecognized proper noun (e.g. a
      place/sect name), the bottom-right overlay appears over the result
      view with the term and a "Duyệt" button.
- [ ] Panel is dismissible via the × and re-appears correctly on the next
      run (state doesn't leak between runs).
- [ ] Confirm this overlay behaves the same way at mobile width (appears
      on top of the stacked layout, not pushed off-screen).

## 9. Settings screen ("Cài đặt dữ liệu")

For each of the three sections (Từ điển cảm xúc / Glossary khởi tạo / Bảng
ngắt nghỉ theo dấu câu):

- [ ] "Tải để sửa" loads current file content into a textarea as JSON.
- [ ] Edit a value, click "Lưu" — success (no error shown).
- [ ] Reload the page, re-open settings, "Tải để sửa" again — edit
      persisted (confirms it actually wrote to disk, not just in-memory).
- [ ] Save deliberately-broken JSON — confirm you get an error message
      instead of a silent failure or a corrupted file on disk.
- [ ] Emotion lexicon: add a brand-new label, save, then run a fresh Alpha
      submission — confirm the new label is a legal option Alpha can now
      choose (indirect check: the dynamic `Literal` type is rebuilt from
      this file at process start, so this specific check requires
      restarting the backend after saving — note that as an expected step,
      not a bug if a same-session run doesn't pick it up immediately).
- [ ] BYOK API key field is visibly present but disabled/inert — confirm no
      network request fires when interacting with it.

## 10. Multi-chapter text

- [ ] Submit text with two clear "Chương N" headings.
- [ ] Confirm Alpha reports the correct chapter count.
- [ ] Confirm the final audio and `.srt` are a single continuous file/track
      spanning both chapters (not two separate downloads).

## 11. Error handling

- [ ] Stop the backend, try to submit — frontend shows a failure state
      rather than hanging forever.
- [ ] Submit with an invalid/missing `GEMINI_API_KEY` — confirm you get a
      clear error, not a silent hang or a 500 with no message.
- [ ] Exhaust the Gemini daily quota (or simulate by submitting ~20+ times)
      — confirm the error surfaces to the UI in some readable form rather
      than the progress bar just freezing indefinitely.

## 12. Docker deployment

- [ ] `docker compose up --build` from a clean checkout brings up all three
      containers without manual intervention.
- [ ] `curl http://localhost/api/voices` returns real JSON (proxy works).
- [ ] Full submit → process → result flow works through `http://localhost`
      (not just localhost:3000/8000 directly) — this is the real check that
      nginx's WebSocket upgrade handling is correct, since a missing
      `Upgrade`/`Connection` header on the `/api/ws/` location silently
      breaks progress streaming while everything else still looks fine.
- [ ] `docker compose down` cleanly stops and removes all three containers
      (confirm with `docker ps -a` — nothing VoxDirector-related left
      running).
- [ ] Restart the stack and confirm the Character Glossary volume persisted
      (a previously-approved term is still known, seed doesn't re-run).
