# VoxDirector AI — Technical Specification for Implementation (v4)

**Document purpose:** Engineering handoff spec for an AI coding agent (Claude Code) to implement VoxDirector AI. This version supersedes v3 — see Section 0.

---

## 0. Changelog

### v4 → v5 — Punctuation-based pausing made conditional on an empirical test

The team will first test whether Piper's own training already produces natural pausing at commas, periods, ellipses, etc. **Only if that test shows it's inadequate** will the punctuation-pause mechanism below be built. This is a pure rule-based (regex) step — deliberately kept out of Beta, since punctuation-to-pause-duration mapping needs no language understanding, only deterministic lookup. See Section 7.3 for the full conditional spec and Section 11's new Step 0.

### v3 → v4 — Agent consolidation (3 agents instead of 4)

The team noticed the former Beta (terminology consistency) and Gamma (expression-word insertion) were doing the same *shape* of work — look up a team-curated table, patch text accordingly, skip rather than guess when uncertain. They are merged into one agent. The former Delta (QA) is renumbered as the third agent in sequence.

| Old name | Old role | New name | New role |
|---|---|---|---|
| Alpha | Chapters + genre/voice + emotion-flagging | **Alpha** | Same, **+ new: flags long-pause points** |
| Beta | Terminology consistency (RAG) | **Beta** | **Merged** — terminology consistency AND expression-word insertion, in one pass, one LLM call per chapter |
| Gamma | Expression-word insertion | *(retired — merged into Beta)* | — |
| Delta | QA (ASR round-trip) | **Gamma** | Same QA role, renamed to be the third agent in the new 3-agent sequence |

**Why merging Beta+Gamma also fixes a real bug risk:** in v3, Gamma had to re-locate Alpha's flagged segments inside text that Beta had already modified, using a fragile text-search-after-the-fact approach. With one agent doing both jobs in a single pass over the same text, that whole problem disappears — there is no intermediate modified-text handoff to search against.

**New in v4:** pause-point flagging (Alpha) and a sentinel-marker mechanism (Beta inserts it, the splitter/postprocess modules consume it) — see Section 6.1 and Section 7.2.

---

## 1. Golden Rule — Read This First

**Do not modify the internal logic of existing pipeline modules unless a section below explicitly says otherwise.** Sanctioned exceptions, all documented in full below: the TTS invocation layer (Piper, Section 5), `subtitle_generator.py`'s timing algorithm (Section 7.1), and now **both `text_splitter.py` and `audio_postprocess.py`** for pause-point handling (Section 7.2). These are deliberate, scoped, documented changes — not a license to refactor these modules generally.

Before writing integration code, **inspect the actual current source** of each file in Section 2.

---

## 2. Existing System Components

| File | Responsibility | Notes |
|---|---|---|
| `text_normalizer.py` | Normalizes raw Vietnamese text into spoken-word form. | No change. Must run *after* Beta and *after* the sentinel marker has been stripped (Section 7.2) — normalizer should never see the marker token. |
| `text_splitter.py` | Splits text into ~250-word chunks. | **Modified (sanctioned)** — must also treat the pause sentinel as a forced boundary. Section 7.2. |
| `audio_postprocess.py` | FFmpeg audio concatenation, silence insertion, music mixing. | **Modified (sanctioned)** — boundaries flagged as pause-points get a longer silence than the ordinary default. Section 7.2. |
| `subtitle_generator.py` | Generates `.srt` subtitles. | Timing algorithm rewritten — Section 7.1 (unchanged from v2/v3). |
| `video_renderer.py` | FFmpeg video rendering, encoder auto-detect. | No change. |
| `make_video.py` | Old CLI entry point. | Retired as entry point; superseded by the FastAPI backend. |
| Piper TTS | Fixed preset voices, no cloning, no built-in emotion/pause tag syntax. | See Section 5. |

---

## 3. Single-Screen User Flow

1. **Landing:** greeting + text input area with drag-and-drop (`.txt`, `.docx`).
2. **Submit → Alpha runs:** returns chapter count, detected genre, suggested voice (editable), and internally produces emotion-flag and pause-point candidates for Beta to act on — not shown as a separate step.
3. **Optional manual inputs:** background image, background music, base pause duration (the *default* inter-chunk silence — separate from Alpha's *extra-long* dramatic pauses, see Section 7.2), subtitle burn-in toggle, QA (Gamma) toggle.
4. **Processing, streamed via WebSocket:** "Reading & understanding text" (Alpha) → "Applying consistency & expression" (Beta) → "Generating voice" (Piper) → "Assembling audio/video" (existing pipeline, now pause-aware) → "Quality check" (Gamma, if enabled).
5. **New-term confirmation panel** (Beta's terminology side) — inline, non-blocking, as before.
6. **Preview & quality**, **segment correction**, **export** — all unchanged from v3.

---

## 4. `.docx` / `.txt` Input Handling
Unchanged from v3.

---

## 5. Piper TTS Integration
Unchanged from v3 in substance. Restating the key constraint that motivates Section 7.2's design: Piper has no built-in syntax for "pause here for longer" — so long dramatic pauses are implemented entirely at the audio-splicing layer (`audio_postprocess.py`), not by asking Piper to do anything special. Piper only ever receives plain, marker-free text.

### 5.1 Genre → Voice Preset Mapping — unchanged
### 5.2 Device Detection — unchanged

---

## 6. Agent Specifications

### 6.0 Shared Conventions
Unchanged — Gemini API via `google-genai`, structured JSON, English keys/Vietnamese values, `CONFIDENCE_THRESHOLD = 0.75`, never block on low confidence.

---

### 6.1 Agent Alpha — Ingestion, Voice-Suggestion & Flagging Agent

**Purpose:** (1) Segment chapters. (2) Detect genre, suggest voice. (3) Flag segments with clear emotional signal. (4) **New:** flag points needing a long dramatic pause.

**Input:** `raw_text: str` + current valid emotion-label set (from the team-uploaded lexicon, Section 6.3's data management subsection — same mechanism as v3, now read by Alpha for labeling and by Beta for insertion).

**Output schema:**
```json
{
  "chapters": [
    {"start_index": 0, "end_index": 1520, "confidence_score": 0.91, "needs_review": false}
  ],
  "detected_genre": "kiem_hiep",
  "suggested_voice_id": "male_deep_01",
  "genre_confidence_score": 0.82,
  "emotion_flagged_segments": [
    {"quoted_text": "Cô ấy cười nói: \"Đúng vậy đó!\"", "emotion_label": "cuoi", "confidence_score": 0.86}
  ],
  "pause_points": [
    {"quoted_text": "...", "reason": "scene transition / long dramatic silence implied", "confidence_score": 0.79}
  ]
}
```

**What counts as a pause point:** a scene break, a beat of silence implied by narration (e.g. "Cả căn phòng chìm vào im lặng."), or a chapter-ending cliffhanger line — text-based evidence only, never inferred purely from "this feels dramatic." If uncertain, do not flag (same no-fallback-needed logic as emotion flags — an unflagged point just means the default pause length applies, which is always a safe outcome).

**System prompt — append to the existing Alpha prompt (chapters + genre, carried over verbatim from v3), add:**
```
NHIỆM VỤ BỔ SUNG (3): Ngoài việc gắn nhãn cảm xúc, hãy tìm các điểm trong văn
bản cần một khoảng ngắt dài hơn bình thường — ví dụ: chuyển cảnh, khoảnh khắc
im lặng được miêu tả rõ trong lời văn, hoặc câu kết chương gây hồi hộp. Với
mỗi điểm tìm được, trích một đoạn văn bản ngắn đặc trưng làm quoted_text kèm
lý do ngắn gọn (reason) và confidence_score. CHỈ dựa trên bằng chứng rõ ràng
trong câu chữ — không suy diễn cảm tính.
```

**Integration point:** Runs once per submission, before Beta. Both `emotion_flagged_segments` and `pause_points` are passed to Beta, which acts on both in the same pass (Section 6.2).

---

### 6.2 Agent Beta — Consistency & Expression Agent (merged)

**Purpose, in one LLM call per chapter:** (1) enforce glossary-consistent terminology (as in all prior versions). (2) Insert human-curated expression words at Alpha's flagged emotion segments. (3) Insert a pause sentinel marker at Alpha's flagged pause points. All three happen against the *same* text in the *same* pass — no cross-agent text handoff, which is what made this safe to merge (see Section 0).

**Input:**
- `chapter_text: str` (from Alpha's chapter split)
- `glossary_context: list[dict]` (RAG-retrieved from ChromaDB, as before)
- `emotion_flagged_segments` and `pause_points` (from Alpha, this same chapter)
- Current emotion lexicon (Section 6.3's data management — `emotion_label → list of candidate words`)
- The pause sentinel token, e.g. `[[PAUSE_LONG]]` (a fixed constant in `config.py`, not something Beta invents)

**Processing:**
1. Terminology pass: exactly as in all prior versions — apply known `canonical_form` values, propose `new_entry_candidates` for anything not in the glossary, never invent a spelling.
2. Expression pass: for each `emotion_flagged_segments` entry, locate `quoted_text` within *this same* `chapter_text` (should be a reliable exact/near-exact match since Beta is working on the original chapter text directly, not a downstream-modified copy). If the lexicon's candidate word for that label isn't already present, insert one (varied across the chapter, not always the same word). If no match is found, skip and note why.
3. Pause pass: for each `pause_points` entry, locate `quoted_text` the same way, and insert the literal sentinel token `[[PAUSE_LONG]]` immediately after the matched point. If no match, skip.

**Output schema:**
```json
{
  "corrected_text": "... (terminology-corrected + expression words + pause sentinels inserted) ...",
  "applied_terms": [{"original": "Red Matt", "canonical_form": "Red Matt"}],
  "new_entry_candidates": [
    {"term": "Huyết Nguyệt Tông", "entity_type": "term", "confidence_score": 0.83}
  ],
  "expression_report": [
    {"matched": true, "emotion_label": "cuoi", "inserted_word": "Haha", "skipped_reason": null}
  ],
  "pause_report": [
    {"matched": true, "skipped_reason": null}
  ]
}
```

**Anti-hallucination rules (combined, apply independently to each of the three passes):**
- Terminology: zero freeform inference — every decision traceable to a specific glossary entry, exactly as in all prior versions.
- Expression: only use lexicon-listed words for the given label; skip rather than guess if no match or word already present.
- Pause: only insert the exact fixed sentinel token; never invent alternative markers; skip if no match.

**System prompt (Vietnamese — verbatim, replaces the separate v3 Beta and Gamma prompts):**
```
Bạn là Beta, biên tập viên phụ trách tính nhất quán thuật ngữ VÀ chèn các
yếu tố biểu cảm/ngắt nghỉ cho một nhà xuất bản sách dịch lâu năm. Bạn cực kỳ
nguyên tắc trên cả hai mặt: chỉ tin vào bảng thuật ngữ đã xác nhận cho tên
riêng, và chỉ dùng từ có trong danh sách được cung cấp cho biểu cảm — không
bao giờ tự "chế" ở bất kỳ phần nào.

VAI TRÒ: Với mỗi chương văn bản, bạn thực hiện ba việc trong một lượt xử lý:
(1) duy trì nhất quán tên riêng/thuật ngữ dựa trên Character Glossary tra
cứu qua RAG; (2) chèn từ biểu cảm phù hợp tại các đoạn được đánh dấu có cảm
xúc; (3) chèn dấu hiệu ngắt nghỉ dài tại các điểm được đánh dấu cần khoảng
lặng.

NGUYÊN TẮC:
- Thuật ngữ: cấm tuyệt đối tự sáng tạo cách viết mới cho thuật ngữ đã có
  trong glossary; thuật ngữ mới chỉ được đề xuất (new_entry_candidates), không
  tự áp dụng.
- Biểu cảm: chỉ chèn từ có trong danh sách lexicon được cung cấp cho đúng
  nhãn cảm xúc; nếu đoạn văn đã có từ biểu cảm tương tự, không chèn thêm.
- Ngắt nghỉ: chỉ chèn đúng token cố định được cung cấp, không tự tạo ký hiệu
  khác.
- Với cả biểu cảm và ngắt nghỉ: nếu không định vị được đoạn văn khớp với
  quoted_text được cung cấp, bỏ qua và ghi rõ lý do — không đoán vị trí khác.

PHONG CÁCH: Output JSON, field tiếng Anh, giá trị text tiếng Việt giữ nguyên
gốc trừ phần được chèn thêm theo đúng quy định trên.
```

**Integration point:** Runs once per chapter, after Alpha, before `text_normalizer.py`. Beta's `corrected_text` (now carrying terminology fixes + expression words + pause sentinels, all at once) is what feeds the normalizer next.

---

### 6.3 Agent Gamma — QA Agent (renamed from Delta)

**Purpose, schema, prompt, and toggle behavior:** identical to the agent named "Delta" in v3 — ASR round-trip via faster-whisper, Word Error Rate, flagged segments, on/off toggle, no speculative error-cause commentary. Only the name changes (third agent in the new 3-agent sequence). Carry the v3 Delta system prompt over verbatim, just referring to the agent as Gamma in code/comments.

---

### Data Management — Human-Curated Uploads (carried over from v3, unchanged in substance)

Emotion lexicon and glossary seed are still team-authored, uploadable, never hardcoded — same file formats and endpoints as v3, with one naming update: the emotion lexicon is now consumed by **Alpha** (for valid label set) and **Beta** (for candidate words to insert), not by a separate "Gamma" as v3 had it (since that agent no longer exists under that name).

The pause sentinel token itself (`[[PAUSE_LONG]]`) is **not** user-uploaded data — it is a fixed technical constant in `config.py`, since it must exactly match what `text_splitter.py` and `audio_postprocess.py` look for in code. Do not make this configurable via the same upload mechanism as the lexicon; keep it a single source-of-truth constant.

---

## 7. Text/Audio Timing Mechanics

### 7.1 Segment-Level Re-render & Subtitle Timing
Unchanged from v2/v3 — measured-duration-based timing (via `ffprobe`) with delta-shift on re-render.

### 7.2 Pause-Point Handling (new)

**Mechanism:** Beta inserts the literal sentinel string `[[PAUSE_LONG]]` into `corrected_text` at each successfully-matched pause point (Section 6.2). This travels through `text_normalizer.py` — **the normalizer must be checked to ensure it passes this token through unchanged rather than trying to "normalize" it as if it were a number or symbol; if the normalizer would mangle it, strip the sentinel out beforehand and re-insert it as chunk metadata rather than inline text.** Verify this against the actual normalizer implementation before assuming inline pass-through works.

**In `text_splitter.py` (sanctioned modification):** when building ~250-word chunks, treat any occurrence of `[[PAUSE_LONG]]` as a forced chunk boundary regardless of the current word count in that chunk (i.e. always end a chunk exactly at the sentinel, even if under 250 words) — then strip the sentinel from the text before that chunk is handed to Piper. Record, per chunk boundary, whether it was a pause-flagged boundary or an ordinary word-count boundary — this per-boundary flag is what `audio_postprocess.py` needs next.

**In `audio_postprocess.py` (sanctioned modification):** accept a per-boundary silence-duration list instead of one single global silence constant. Ordinary boundaries get the existing default (now user-adjustable per Section 3, step 3). Boundaries flagged as pause-points get a longer duration — define `PAUSE_LONG_DURATION_MS` in `config.py` as a separate constant from the ordinary default, with a sensible starting value (e.g. 1200–1500ms vs. an ordinary ~300–500ms default) to be tuned empirically once the team listens to real output.

---

### 7.3 Punctuation-Based Pause Handling (Conditional — Test Before Building)

**Do not build this section's mechanism until the empirical test in Section 11, Step 0 has actually been run and has shown it necessary.** If Piper's own training already produces acceptable natural pausing at punctuation, skip this entire section — the pipeline stays exactly as Sections 6–7.2 describe, with no additional punctuation-handling step.

**If the test shows Piper's natural pausing is inadequate, build as follows:**

**Where it lives:** a pure rule-based (regex) function, not an LLM agent, not part of Beta. Runs after Beta, after `text_normalizer.py`, immediately before `text_splitter.py` — operating on final, normalized text just before it gets chunked for Piper.

**Mechanism:** for each punctuation mark matched by regex, insert a short numbered sentinel token (e.g. `[[PAUSE_P_1]]`, `[[PAUSE_P_2]]`, ... — reuse the same sentinel *pattern* as `[[PAUSE_LONG]]` from Section 7.2, but these are much shorter, much more frequent pauses, so they should NOT force a chunk boundary the way `[[PAUSE_LONG]]` does — see the distinction below). `text_splitter.py` and `audio_postprocess.py` need to treat these two sentinel families differently:
- `[[PAUSE_LONG]]` (Section 7.2, from Alpha/Beta's dramatic-pause flagging) → forces a chunk boundary, gets a long silence.
- `[[PAUSE_P_n]]` (this section, from punctuation, if built at all) → does **not** force a chunk boundary by itself (that would fragment audio into far too many tiny clips, causing audible "seams" — the exact risk flagged before building this). Instead, these are resolved *within* Piper's synthesis of a chunk if Piper can accept inline pause hints in its input format, OR (if Piper cannot) they are used to further subdivide only at natural sentence boundaries within a chunk, synthesize those sub-pieces separately, and concatenate with the correspondingly short silence — verify which of these two paths Piper's actual API supports before implementation; do not assume.

**Human-curated punctuation-to-duration table** (uploadable, same philosophy as the emotion lexicon in Section 6.3 — team can edit without touching code), stored at `data/punctuation_pauses.json`:

```json
{
  ",": 150,
  ".": 400,
  "!": 400,
  "?": 400,
  "...": 700,
  "…": 700,
  ";": 300,
  ":": 300,
  "-": 200,
  "–": 200,
  "—": 250,
  "(": 100,
  ")": 100,
  "\"": 50,
  "'": 50,
  "“": 50,
  "”": 50,
  "?!": 500,
  "!?": 500
}
```

**Important edge case — the Vietnamese dialogue dash:** a `-` at the *start* of a line (e.g. `- Anh đi đâu đấy?`) marks a new speaker's dialogue line in Vietnamese literary convention — this is a different function from a mid-sentence hyphen or en-dash used parenthetically, and likely warrants a different (probably longer) pause than the generic `-`/`–` entries above, plus different regex detection (anchored to line-start, not any `-` character anywhere). Treat this as a **separate table key** (e.g. `"dialogue_dash_line_start": 350`) with its own regex pattern (`^\s*-\s`), not the same key as a generic hyphen. Flag this to the team as needing its own test/tuning pass, since it's the most linguistically-specific case in this table.

**Backend endpoint:** add `POST /api/settings/punctuation-pauses` and `GET /api/settings/punctuation-pauses` alongside the emotion-lexicon endpoints in Section 6.3's data management subsection — same replace-on-upload behavior.

---

## 8. Frontend & Backend Architecture

Unchanged from v3's structure, with these renames/adjustments:
- `agents/gamma_prosody.py` (v3, retired) is removed; `agents/delta_qa.py` is renamed `agents/gamma_qa.py`.
- `agents/beta_consistency.py` now contains the merged consistency+expression logic (absorbing what would have been a separate expression module).
- `DataManagementPanel.tsx` (frontend) unchanged in purpose, just reflects that the lexicon now visibly feeds "Alpha + Beta" rather than a separate Gamma, if the UI displays any such labeling to the user at all (likely not necessary — this is an implementation detail, not user-facing).

---

## 9. Acceptance Criteria (KPIs)

All KPIs from v3 remain, with the emotion-match-rate KPI now measured against Beta's single-pass matching (Section 6.2) instead of a separate cross-agent handoff — the target (>90% match rate) and rationale are unchanged, just the responsible component changed. Add:

| Metric | Target | How to measure |
|---|---|---|
| Pause-point match rate | >90% of Alpha's flagged pause points successfully matched by Beta in the same pass | Test set, log `matched: false` rate for `pause_report` |
| Pause duration audible difference | Long pauses perceptibly longer than ordinary inter-chunk silence on playback | Human listening check, not an automated metric |

---

## 10. Environment / Dependencies
Unchanged from v3.

---

## 11. Suggested Build Order

**Step 0 — Empirical test gate (do this before anything else in this list):** Synthesize a test paragraph with Piper containing a comma, a period, a question mark, an exclamation mark, an ellipsis, and at least one Vietnamese dialogue-dash line. Listen to the output. If pausing already sounds natural and adequate, **do not build Section 7.3 at all** — proceed directly to Step 1 below with the pipeline as described in Sections 6–7.2 only. If pausing is inadequate (too abrupt, no distinction between comma and period, etc.), build Section 7.3 as an additional step inserted between "modify `text_splitter.py`" and "modify `audio_postprocess.py`" in the numbered list below. Report the test result before proceeding either way.

1. `config.py` (including `CONFIDENCE_THRESHOLD`, genre→voice table, and now `PAUSE_LONG_TOKEN` + `PAUSE_LONG_DURATION_MS`), device detection, `llm_client.py`.
2. Piper standalone test (RTF measurement on this machine's CPU).
3. Set up `data/` directory + upload endpoints (emotion lexicon, glossary seed) — needed before Alpha/Beta can be meaningfully tested.
4. Agent Alpha — chapters + genre/voice + emotion-flagging + pause-point-flagging. Test standalone on sample text covering all four responsibilities.
5. Agent Beta (merged) — test all three passes independently on sample chapters: (a) terminology correction alone, (b) expression insertion alone, (c) pause sentinel insertion alone, then (d) all three together on one realistic chapter.
6. Modify `text_splitter.py` for sentinel-based forced boundaries (Section 7.2) — test with a synthetic chapter containing a deliberately-placed sentinel mid-chunk.
7. Modify `audio_postprocess.py` for per-boundary variable silence duration (Section 7.2) — test that a pause-flagged boundary is audibly longer than an ordinary one.
8. Subtitle timing algorithm (Section 7.1) — as before.
9. FastAPI backend, wired end-to-end: Alpha → Beta → normalizer → (sentinel-aware) splitter → Piper → (variable-silence) postprocess → subtitle → video.
10. Segment re-render endpoint.
11. Agent Gamma (QA) + toggle.
12. Next.js frontend.
13. Settings screen + BYOK flow.
14. Local end-to-end test, including at least one sample with a genuine pause point and one with a genuine emotion segment, confirmed audible on playback.
15. VPS deployment.

---

## 12. Deployment Workflow
Unchanged from v3 — local-first, then VPS + purchased domain, Docker Compose (FastAPI + Next.js + nginx + certbot).

---

## 13. Open Decisions Needing Team Confirmation

0. **Section 7.3 is entirely conditional on the Step 0 test result (Section 11).** Claude Code should not write any punctuation-pause code until the team reports back that the test showed it's needed.
1. **`PAUSE_LONG_DURATION_MS` starting value** — proposed 1200–1500ms vs. an ordinary ~300–500ms default; needs empirical tuning once the team listens to real output.
2. **Whether `text_normalizer.py` passes the sentinel token through safely** (Section 7.2) — flagged as needing verification against actual source; if it doesn't, the fallback (strip-and-carry-as-metadata) needs to be built instead of inline pass-through.
3. Carried over from v3, still unresolved: emotion word placement heuristic refinement, word-selection strategy for multi-candidate lexicon entries, real genre labels + Piper voice IDs, default fallback background image, BYOK key storage confirmation.
