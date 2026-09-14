# VoxDirector AI — Session Handoff (2026-09-15, end of session)

**Written for a fresh session with zero memory of this conversation.** Read
this file first, in full, before touching code. It supersedes nothing —
`HANDOFF_2026-09-13_END_OF_SESSION.md` (same folder) covers everything from
the session before this one (Phases 0-4 of the master plan, all deployed);
`ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md` still has the original
master-plan reasoning. This file records what changed in THIS session, what's
still open, and the sharp edges a new session will hit immediately.

## 1. What happened this session, in order

Commits, newest first (`git log --oneline -8` on branch `VoxDirector`):

```
1983e42 Give all 3 Data Settings sections their own large responsive dialog
2043f06 Split Glossary into its own tabbed dialog, separate from Data Settings
ee57946 Fix glossary visibility, wire up BGM mixing, add ChromaDB glossary export
ada44cc Fill in real Gemini fallback models and pricing from official docs
4bb4a9b Fix 413 on background-image upload: set nginx client_max_body_size
ee110bf Close out Alpha/Gamma checklist: model resilience, audio-health checks, cost tracking
382c2a5 Replace raw JSON textarea with visual editors for the 3 data settings
```

**All 7 are LOCAL ONLY — none pushed.** Same standing rule as last session:
only push (`git push vox VoxDirector`) when the user explicitly asks.
`origin` = upstream SDK (never push there), `vox` = user's own repo.

Working tree is clean. `.mcp.json` (untracked, root of repo) is not mine —
leave it alone, it predates this session.

### What actually changed, in build order

1. **Settings UI overhaul** — replaced the raw `JSON.stringify()`-in-a-
   `<textarea>` for all 3 data-settings files with real visual editors:
   `EmotionLexiconEditor.tsx` (chip lists per label), `GlossaryEditor.tsx`
   (entry cards), `PunctuationPauseEditor.tsx` (slider + number per
   punctuation mark). This was the deferred item flagged at the end of the
   *previous* session.

2. **Closed out 3 items from the Alpha/Gamma "still needs work" checklist**
   (the other items — Alpha eval set, Beta emotion-tag expansion, Beta
   listening verification — are still blocked on human input, see below):
   - **Gemini model resilience**: `voxdirector/llm_client.py` now resolves a
     fallback model (`config.GEMINI_MODEL_FALLBACKS`) if the primary fails,
     but ONLY ONCE per backend process (never mid-job) — preserves the
     existing "1 model per pipeline run, reproducible" invariant. Two real
     bugs were caught and fixed while building this: an early draft would
     have serialized every Gemini call server-wide (lock held across the
     network call), and the final-fallback-exhausted path was rewrapping the
     original exception in a new `RuntimeError`, breaking the existing
     `tests/test_llm_client.py` suite (fixed to re-raise the original
     exception type).
   - **Gamma audio-health checks**: `voxdirector/agents/gamma_qa.py::check_audio_health()` —
     clipping, near-total silence, unexpected internal silence gaps, via
     stdlib `wave` + numpy (no new dependency). Wired into per-chunk
     flagging AND into the existing retry-and-pick-best acceptance
     criteria, so a clipped/silent segment now auto-retries same as a
     low-ASR-confidence one. Verified against synthetic WAV fixtures.
   - **Per-job Gemini token/cost tracking**: `voxdirector/usage_tracker.py`
     (new) accumulates real token counts per job_id — contextvar-propagated
     through `asyncio.to_thread`, dict-keyed so it survives the
     `/api/submit` → WebSocket request boundary. Cost estimate reads
     `data/gemini_pricing.json` (ships with real numbers now, see below).

3. **Fixed a real nginx bug**: `client_max_body_size` was never set, so
   nginx defaulted to 1MB and 413'd any background-image upload over that —
   reported by the user as "Error: Failed to load background image (413)".
   Fixed in `deploy/nginx/nginx.conf` (now 20M, scoped to the whole server
   block since a long manuscript's JSON body could hit the same limit).

4. **User supplied real research links + a new API key**:
   - `GEMINI_MODEL_FALLBACKS` now defaults to `gemini-3.5-flash,gemini-2.5-flash`
     (verified via `https://ai.google.dev/gemini-api/docs/models` — both
     confirmed stable, not on Google's shut-down list).
   - `data/gemini_pricing.json` filled in with real pricing (verified via
     `https://ai.google.dev/gemini-api/docs/pricing`) — `_placeholder` is
     now `false`. **Note**: the 3.6/3.7/3.8 Flash pricing is promotional
     through 2026-12-31, roughly doubles 2027-01-01 — needs revisiting then.
   - **The new API key the user supplied is ALSO dead** — same
     `401 UNAUTHENTICATED / ACCESS_TOKEN_TYPE_UNSUPPORTED` as the one from
     last session, and the same `AQ.`-prefix/~53-char shape (an OAuth
     access token, not a real API key). Told the user clearly: they need a
     key starting `AIzaSy...` (~39 chars) from `aistudio.google.com/apikey`,
     not whatever they're currently copying. **Still no working Gemini key
     as of end of session.**

5. **Fixed 3 user-reported bugs in one pass** (glossary/BGM/ChromaDB):
   - **"Approved terms don't show up in Data Settings"**: NOT a save bug —
     `approve_new_entries()` was already writing correctly to ChromaDB.
     Proved this live: `GET /api/glossary` returned the user's own
     previously-approved terms. The actual bug: the Settings UI only ever
     showed `data/glossary_seed.json` (a static bootstrap file), with no UI
     surface for the live ChromaDB collection at all. Added
     `GET/POST/DELETE /api/glossary` + `LiveGlossaryManager.tsx` (new CRUD
     panel), plus keyword-heuristic label suggestion (`voxdirector/glossary/label_suggestion.py`,
     no LLM call) for terms added manually without a chosen type.
   - **BGM mixing "doesn't work"**: `pipeline/audio_postprocess.py::mix_bgm()`
     existed but was NEVER called from the backend — no upload endpoint, no
     wiring — same "written but never integrated" pattern as
     `video_renderer.py` from two sessions ago. Added
     `POST /api/background-music/{job_id}` + a volume slider. Found and
     fixed 2 real bugs in `mix_bgm()` itself while verifying live: no
     resample guard for a BGM file at a different sample rate than the
     voice track, and ffmpeg's `amix` defaulting to `normalize=1` — which
     was silently **halving the main narration's volume** whenever BGM got
     mixed in (measured: voice RMS 0.1022 → 0.0592). Added
     `orchestrator.rebuild_final_audio()` to replace 3 existing
     `assemble_final_audio()` call sites, since calling that function
     directly at any of them would have silently wiped out the BGM mix on
     the next QA-retry or `/api/rerender`.
   - **ChromaDB visualizer**: `scripts/export_chromadb_glossary.py` —
     pandas → CSV + browsable HTML, read-only (CRUD lives in the new
     Settings panel instead). Copied into the backend Docker image
     (`COPY scripts /app/scripts` added to `backend/Dockerfile`) so it runs
     via `docker exec ... python /app/scripts/export_chromadb_glossary.py`
     against the real persisted volume.

6. **Data Settings dialog redesign** (2 rounds, user-directed):
   - Round 1: pulled Glossary (seed editor + live manager) out of the
     cramped "Cài đặt dữ liệu" list into its own bigger tabbed dialog
     (`GlossaryManagerDialog.tsx`, new `ui/tabs.tsx` wrapper).
   - Round 2 (user: "I don't want dictionary/emotion/pause data displayed
     together in one popup"): applied the same big-dialog treatment to ALL
     3 sections via one shared `DataViewerDialog.tsx` — sized
     `width:min(80vw,84rem)` / `height:min(80vh,48rem)` on desktop
     (min-height 60vh floor), full-screen sheet below the `sm` breakpoint
     on mobile. Approved design: opening any big dialog closes the small
     "Cài đặt dữ liệu" one behind it ("option A"), not stacked.

     **Found and fixed 2 real architectural bugs while verifying this
     live** (both confirmed via direct DOM/`data-*`-attribute inspection,
     not screenshots — screenshots were unreliable all session because the
     automation tab kept losing focus/visibility, which throttles CSS
     transitions and produces misleading `getBoundingClientRect()`/opacity
     readings; cross-checked against `document.visibilityState` every time
     to rule that out before concluding a real bug):
     1. A plain `onClick` on `DialogTrigger` to close the parent silently
        didn't fire reliably (has to pass through several layers of
        base-ui's internal event composition). Fixed by switching to
        `onOpenChange` — base-ui's actual controlled-component hook.
     2. That STILL failed a different way: the big dialogs were nested
        inside the small dialog's own `DialogContent` in the JSX tree. When
        the parent's close animation finished and its DOM node got
        removed, the child dialog nested inside it unmounted too — even
        mid-`open=true` — because React portals stay tied to the *owning
        component tree*, not wherever they visually render in the DOM.
        Fixed by lifting all open/close state to `SettingsPanel.tsx` and
        rendering all 4 dialogs as **siblings**, none nested inside
        another's `DialogContent`. This is the load-bearing fix — if a
        future session adds a 4th data dialog, it MUST also be a sibling,
        not nested, or the same bug recurs.

   - `SettingsSectionShell` and `LiveGlossaryManager` simplified to
     auto-load on mount (dropped their own "Tải để sửa"/"Tải để xem" gate
     buttons) — opening a dedicated dialog already IS the "show me this"
     signal now that each section has its own space.

7. **Emotion dictionary — investigated, did NOT add fabricated data.**
   User asked to "add all emotions you know" to the emotion lexicon. Before
   doing that, ran a live empirical test (synthesize with a candidate
   bracket tag → transcribe with Gamma's own Whisper → check whether the
   tag word appears in the transcript) rather than trusting the README
   citation from 2 sessions ago. Result: **confirmed real** —
   `[cười]` adds 0.64s of genuine non-verbal audio and never appears in the
   transcript. **Confirmed fake for all 9 other candidates tested**
   (`[khóc]`, `[la hét]`, `[thì thầm]`, `[rên rỉ]`, `[ho]`, `[hắt hơi]`,
   `[ngáp]`, `[nấc nghẹn]`, `[run rẩy]`) — every one got read aloud as a
   literal word, silently injecting unintended content into the narration
   (e.g. `[khóc]` produced "...nói xong **khóc** rồi bỏ đi", adding a verb
   that wasn't in the source text). Also confirmed `vieneu==3.6.4`
   (currently pinned) is already the latest PyPI release — no newer version
   to check for expanded tag support. **`data/emotion_lexicon.json` was
   NOT touched this session** — there is currently no safe way to expand it
   beyond the 3 labels already there. Told the user clearly why, with the
   test evidence, instead of silently complying or silently refusing.

## 2. Known blockers / sharp edges for the next session

- **Gemini API key is STILL dead** (2 dead keys in a row now, both
  `AQ.`-prefixed OAuth-access-token-shaped, not `AIzaSy...`-prefixed real
  API keys). This blocks: Alpha/Beta live runs, the Alpha eval set, Beta
  emotion-tag expansion (moot now — see item 7 above), Beta live listening
  verification, and live-testing the Gemini model-fallback mechanism
  against a *real* API failure (only unit-tested + tested against the dead
  key's 401, which correctly does NOT trigger fallback since 401 isn't
  404 — by design, see `llm_client.py`). **Next session: check if the user
  has gotten a real `AIzaSy...` key before assuming anything Gemini-related
  works.**
- **Screenshots are unreliable in the browser automation tool** — the
  in-app browser tab periodically loses focus/visibility mid-session
  (`document.visibilityState` flips to `"hidden"`), which throttles CSS
  animations and makes `screenshot`/`getBoundingClientRect()` show stale or
  mid-transition frames. This produced multiple false-alarm "bugs" this
  session before the real ones were found. **When testing UI live, prefer
  direct DOM/JS inspection (`javascript_tool`, checking `data-open`/
  `data-closed`/computed styles/`document.visibilityState`) over trusting a
  single screenshot** — this is what actually caught the 2 real dialog bugs
  in section 1.6 above, after screenshots gave misleading signals.
  `read_page`/`find` also traverse portal-rendered dialog content
  inconsistently depending on `filter` mode — don't trust an empty result
  from `filter: "all"` rooted at `main` as proof a dialog is closed.
- **Containers stop on their own sometimes** (same as last session's
  handoff note — Docker Desktop/host sleeping, not app-related). Always
  `docker ps -a` before debugging "it's stuck."
- **Docker rebuild/restart pattern unchanged** from last session:
  ```bash
  cd "E:/tool audio/VieNeu-TTS"
  docker compose build backend frontend
  GEMINI_API_KEY="<key>" docker compose up -d
  for i in $(seq 1 15); do
    code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/voices)
    [ "$code" = "200" ] && break
    sleep 2
  done
  ```
  Backend Dockerfile now also copies `scripts/` (needed for
  `export_chromadb_glossary.py` to run via `docker exec`).

## 3. Explicitly deferred / not done — don't assume these are bugs

- **`data/emotion_lexicon.json` still has only 3 labels** — this is now a
  *verified* ceiling (see section 1.7), not an oversight. Don't add more
  without either a newer VieNeu-TTS release documenting new tags, or
  another live test proving a specific candidate tag is genuinely
  recognized (transcript-absence + real duration increase, same method
  used this session).
- **`data/eval_set/cases.json`** — still empty, still blocked on the dead
  Gemini key + needing real graded chapters from the user.
- **Voice cloning** — explicitly out of scope now; the user said "leave it
  to me" this session. Don't revisit unless they bring it up again.
- **Gemini pricing table** will need a manual update around 2027-01-01 when
  the promotional pricing for the 3.6/3.7/3.8 Flash tier expires (see
  `data/gemini_pricing.json`'s own `_note`).

## 4. Practical conventions that worked this session (keep doing these)

- **Test in the actual running app via direct evidence, not assumption** —
  caught every real bug this session this way: the nginx 413 (reproduced
  with a real oversized upload before AND after the fix), the BGM
  volume-halving bug (measured RMS before/after with numpy, not just
  "sounds about right"), the 2 nested-dialog bugs (DOM attribute inspection
  after screenshots gave false signals), and the emotion-tag finding
  (actual synthesize + transcribe, not re-trusting a 2-session-old README
  citation). This project's existing "verify, don't assume" norm keeps
  paying off — don't skip it under context-window pressure.
- **No fabricated data, ever** — blocked the "add all emotions" request
  this session exactly the way it blocked the eval set and voice cloning
  in earlier sessions. When a user asks for something that would require
  inventing unverified data, the answer is investigate-and-explain, not
  silent compliance or silent refusal.
- **Commit locally after each verified chunk of work, don't push** — 7
  commits this session, all local. Only push on explicit request.

## 5. Quick file map for what changed this session

- `voxdirector/llm_client.py`, `voxdirector/usage_tracker.py` (new) —
  Gemini model resilience + token tracking.
- `voxdirector/agents/gamma_qa.py` — `check_audio_health()`.
- `voxdirector/orchestrator.py` — `rebuild_final_audio()` (BGM-aware
  wrapper, replaces direct `assemble_final_audio()` calls in
  `backend/app/main.py`).
- `voxdirector/glossary/store.py`, `voxdirector/glossary/label_suggestion.py`
  (new) — live glossary CRUD + keyword label suggestion.
- `pipeline/audio_postprocess.py` — `mix_bgm()` fixes (aresample,
  `normalize=0`).
- `deploy/nginx/nginx.conf` — `client_max_body_size 20M`.
- `data/gemini_pricing.json` — real pricing, `_placeholder: false`.
- `scripts/export_chromadb_glossary.py` (new).
- `backend/app/main.py` — `/api/glossary` CRUD endpoints,
  `/api/background-music/{job_id}`, usage-tracker wiring.
- `backend/Dockerfile` — `COPY scripts /app/scripts`.
- Frontend: `EmotionLexiconEditor.tsx`, `GlossaryEditor.tsx`,
  `PunctuationPauseEditor.tsx`, `LiveGlossaryManager.tsx`,
  `GlossaryManagerDialog.tsx`, `DataViewerDialog.tsx` (new),
  `SettingsSectionShell.tsx`, `SettingsPanel.tsx`, `ui/tabs.tsx` (new) —
  the full Settings UI overhaul across both rounds.
