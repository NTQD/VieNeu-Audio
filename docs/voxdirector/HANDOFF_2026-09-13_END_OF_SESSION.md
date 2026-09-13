# VoxDirector AI — Session Handoff (2026-09-13, end of session)

**Written for a fresh session with zero memory of this conversation.** Read
this file first, in full, before touching code. It supersedes nothing —
`docs/voxdirector/ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md` still has
the full 5-phase master plan and reasoning; `PHASE0_HANDOFF.md` (same
folder) has the original project architecture writeup. This file exists
because **all 5 phases of that master plan are now done** — it records
exactly what changed, what's still open, and the sharp edges a new session
will hit immediately if it doesn't know about them.

## 1. What happened this session, in order

Starting from Phase 0 already complete (see `PHASE0_HANDOFF.md`), this
session implemented **Phase 1 through Phase 4 of the master plan**, plus
two rounds of live bug fixes the user found by actually using the app.
Every phase was planned via `EnterPlanMode`/`ExitPlanMode` (approved by the
user each time), implemented, and **verified live against the running
Docker app** before committing — not just code-reviewed.

Commits, newest first (`git log --oneline -8` on branch `VoxDirector`):

```
d7cacaa Fix Alpha silently dropping trailing text, add spinner to progress stepper
e9baba5 Fix silent settings-caching bug, lower QA retry sensitivity
1eaed33 Phase 4: Gamma auto-retry, per-word confidence, recalibrated flagging
5cd1abd Phase 3: Beta chapter chunking, diff view, shared text-utils refactor
4a11646 Phase 2: Alpha map-reduce windowing, richer genre tags, fuzzy quote rescue
ab93c31 Phase 1: SQLite job/trace persistence + Alpha eval harness
c1f5dc7 Phase 0: wire up glossary approve, expression/pause reports, needs_review, QA summary
867b124 Add Phase 0 handoff doc for context-window continuity
```

**All 7 of these commits are LOCAL ONLY — none have been pushed.** The
user explicitly asked (mid-session) to stop auto-pushing: *"every time you
change the code, you don't have to push it to github right away, you just
need to sync it with local git."* Only push when the user explicitly asks
(`git push vox VoxDirector`). Two remotes exist: `origin` = upstream SDK
(never push here), `vox` = the user's own repo (push here, only when asked).

### Phase-by-phase summary (what actually changed, not what the plan said)

- **Phase 1 (Persistence & measurement)**: `voxdirector/db.py` (new) — a
  SQLite job/chapter/eval trace log (`voxdirector/.data/voxdirector.db`,
  own Docker volume). `scripts/run_eval.py` + `data/eval_set/` — an eval
  harness for Agent Alpha. **`data/eval_set/cases.json` is still
  deliberately empty** — a real eval set needs real graded chapters and
  human judgment, which can't be fabricated (this project has a hard "no
  fabricated data" norm, stated repeatedly by the user and baked into
  `PHASE0_HANDOFF.md`'s working conventions). If the user has since added
  real cases there, `python scripts/run_eval.py` will use them.

- **Phase 2 (Alpha: scale and precision)**: map-reduce windowing for long
  novels (`voxdirector/agents/alpha_ingestion.py`, `ALPHA_WINDOW_CHARS`),
  richer genre/tone/pacing/audience tags driving a real voice-scoring
  function (`voxdirector/voice_scoring.py`, new) instead of a flat
  genre→voice lookup, and fuzzy-match rescue for paraphrased quotes. Two
  real bugs were found and fixed *during* this phase by testing live with
  real Gemini calls, not assumed away — see the commit message for
  `4a11646` if debugging anything in this area.

- **Phase 3 (Beta: chunking + transparency)**: chapter chunking for
  oversized chapters (`BETA_CHUNK_CHARS`), a word-level diff view
  (`DiffView.tsx`, new) showing what Beta actually changed — `corrected_text`
  had been computed since day one and never reached the frontend, same
  "agent computes it, product discards it" pattern as Phase 0. Also
  extracted `voxdirector/text_utils.py` (new) — three near-duplicate
  copies of windowing/normalize/filter logic had accumulated across
  `alpha_ingestion.py`, `orchestrator.py`, and `backend/app/main.py`; now
  one shared module. **Voice cloning (master-plan item 10) was
  investigated and confirmed technically real** (`vieneu`'s local
  `infer()` genuinely supports `ref_audio=<path>` for instant cloning) but
  **deliberately not implemented** — the user chose to skip it since
  there's no library of real recorded reference clips and none can be
  fabricated. Revisit only if the user brings real audio clips.

- **Phase 4 (Gamma: from reporter to corrector)**: per-word ASR confidence
  (`faster-whisper` was never even called with `word_timestamps=True`
  before — confirmed by reading the installed package's own signature,
  not assumed), recalibrated flagging (WER *or* any low-confidence word),
  and automatic retry-and-pick-best
  (`voxdirector/orchestrator.py::retry_flagged_segment()`/
  `verify_and_retry_chapter_quality()`) — confirmed live via a byte-hash
  comparison that VieNeu-TTS is genuinely stochastic before relying on
  that as the premise. **Real cost tradeoff observed live, not
  theoretical**: QA on a 2-chunk chapter with one retry took ~273s on
  CPU. On the user's real 2013-word chapter, 4 of 5 chunks got flagged
  and QA took the better part of an hour — this directly motivated the
  next fix.

- **Post-Phase-4 live bug fixes** (both found because the user was
  actually using the app, not from code review):
  1. **Settings cache bug**: editing the emotion dictionary or
     punctuation-pause table via the Settings UI wrote the file correctly
     but the running backend kept serving its in-memory cached copy
     forever — no error, just silent no-op until a manual restart. Fixed
     with `invalidate_*_cache()` functions wired into the corresponding
     `POST /api/settings/*` endpoints. Also lowered
     `GAMMA_WORD_CONFIDENCE_THRESHOLD` from 0.35 → 0.15 (0.35 was flagging
     ~80% of chunks on a real chapter — too sensitive for faster-whisper's
     actual Vietnamese confidence distribution).
  2. **Real content-loss bug**: `_clamp_and_sort()` in
     `alpha_ingestion.py` clamped chapter-boundary indices into range but
     never forced the *first* chapter to start at 0 or the *last* chapter
     to end at the true text length. When Gemini's reported boundaries
     didn't perfectly span the whole document (common — not pixel-exact
     about offsets), whatever text fell outside every chapter's range was
     silently dropped — never reached Beta or TTS. This is almost
     certainly what the user meant by "text is always cut off at the end
     when Alpha and Beta are on." Fixed with new `_close_coverage_gaps()`,
     verified with 4 deterministic test scenarios (trailing gap — the
     exact reported case, leading gap, middle gap, already-correct no-op).
     **Could not be verified live end-to-end** — see blocker below.
  3. Also added a rotating jade-green spinner ring to the active stage in
     `frontend/src/components/ProgressStages.tsx` (replacing a plain
     opacity pulse), per direct request.

## 2. Known blockers / sharp edges for the next session

- **The user's Gemini API key is dead.** Confirmed by calling Google's
  API directly with it (not assumed): `401 UNAUTHENTICATED`. The key is
  `AQ.`-prefixed (~53 chars) — this looks like a short-lived OAuth-style
  access token, not a permanent API key (Google AI Studio issues
  `AIzaSy...`-prefixed keys, ~39 chars, which don't expire this way). It
  worked for several hours earlier in this same session, then stopped —
  consistent with OAuth token expiry, not a one-off glitch. **The user
  will need to supply a fresh key** (ideally the permanent `AIza...` kind
  from `aistudio.google.com/apikey`) before Alpha/Beta can run again.
  **This means Phase 4's `_close_coverage_gaps()` fix has only been
  verified with deterministic unit tests, not a live Alpha+Beta run on a
  real chapter** — that should be the first thing done once a working key
  is available.

- **A second, separate landmine**: this Windows machine has a *persistent
  OS-level* `GEMINI_API_KEY` environment variable (unrelated to this
  project, likely from some other Gemini CLI tool) that **shadows**
  whatever is in the project's own `.env` file, because Docker Compose's
  variable substitution prefers the shell environment over `.env`. Symptom
  if you hit this: Alpha/Beta calls fail with the exact same `401
  UNAUTHENTICATED` / `ACCESS_TOKEN_TYPE_UNSUPPORTED` error, even right
  after confirming `.env` has a correct key. **Always start/restart the
  backend with an explicit inline override**, don't rely on `.env` alone:
  ```bash
  cd "E:/tool audio/VieNeu-TTS"
  GEMINI_API_KEY="<the real key>" docker compose up -d
  ```
  Verify which key actually landed inside the container before debugging
  anything else:
  ```bash
  docker exec vieneu-tts-backend-1 sh -c 'echo -n "$GEMINI_API_KEY"'
  ```

- **Containers stop on their own sometimes.** Twice this session, all
  three containers (`backend`/`frontend`/`nginx`) were found stopped
  (clean exit codes, not crashes) with no action from either the user or
  Claude — almost certainly Docker Desktop or the host machine sleeping.
  **Job state lives only in an in-memory Python dict** (`JOBS` in
  `backend/app/main.py`), so a stopped container loses any in-progress
  job permanently — there's nothing to resume, just resubmit. Always
  `docker ps -a` before assuming "it's stuck" — check whether the
  container is even running before debugging application logic.

- **QA (Gamma) is slow on CPU, by design now, not a bug** — the Phase 4
  auto-retry mechanism means a flagged chunk gets re-synthesized and
  re-verified with Whisper up to `GAMMA_MAX_RETRIES` (default 2) times.
  This is real, deliberate compute, not a hang. Tunable via env vars if
  needed: `VOXDIRECTOR_GAMMA_MAX_RETRIES`,
  `VOXDIRECTOR_GAMMA_WORD_CONFIDENCE_THRESHOLD`,
  `VOXDIRECTOR_GAMMA_FLAG_CUTOFF_MULTIPLIER`. If a GPU is available,
  `docker-compose.gpu.yml` (already built, from before this session)
  would meaningfully help.

## 3. Explicitly deferred / not done — don't assume these are bugs

- **Visual editors for the 3 data-settings JSON files** (emotion
  dictionary, glossary seed, punctuation pauses). The user directly
  asked "do you want a visual interface or a JSON code box you don't
  understand" — they clearly want a proper UI, not the current raw
  `JSON.stringify()`-in-a-`<textarea>` (`frontend/src/components/SettingsPanel.tsx`).
  When explicitly asked to prioritize, the user chose **"just the two
  backend fixes for now"** (cache bug + QA threshold) and deferred the
  visual editors. This is real, wanted, not-yet-started work — worth
  raising proactively if the user doesn't bring it up again.
- **SQLite vs. MySQL**: the user asked why SQLite instead of MySQL for
  the Phase 1 job-trace log. Answer given: SQLite was a deliberate choice
  matching the project's own documented scale ("~3 beta testers", per
  `PHASE0_HANDOFF.md`'s working conventions), not because MySQL is
  unsuitable for a VPS. Offered to switch if the user's plans have grown.
  **No decision was made** — this is open, not resolved.
- **Voice cloning** (master-plan item 10) — see Phase 3 summary above.
  Infrastructure not built; needs real reference audio clips first.
- **`data/eval_set/cases.json`** — still empty. Needs the user to add
  real graded chapters per `data/eval_set/README.md`.

## 4. Practical conventions that worked this session (keep doing these)

- **Plan Mode for anything touching core agent logic**: every phase (1-4)
  went through `EnterPlanMode` → research/design → `ExitPlanMode` →
  explicit user approval before writing code. This caught real design
  flaws before they shipped (e.g., the voice-scoring weight rebalance in
  Phase 2, the "keep best not last" retry logic in Phase 4).
- **Test in the actual running app, not just code review** — this
  project's own stated norm, and it caught real bugs every single time
  it was actually followed (the chapter-boundary reconciliation redesign
  in Phase 2, the `GlossaryEntry.first_seen_chapter` crash in Phase 0,
  the settings-cache bug, the truncation bug). Code review alone would
  have missed all of these.
- **Docker rebuild/restart pattern** (code is baked into images, no bind
  mounts):
  ```bash
  cd "E:/tool audio/VieNeu-TTS"
  docker compose build backend frontend
  GEMINI_API_KEY="<key>" docker compose up -d
  # then poll until ready (first boot loads models, can take 30-90s+):
  for i in $(seq 1 15); do
    code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/voices)
    [ "$code" = "200" ] && break
    sleep 2
  done
  ```
- **Browser testing gotcha**: the in-app browser pane sometimes carries
  over a custom/mobile viewport size from a previous session, which
  desyncs click coordinates from what `find`/screenshots report. If
  clicks land on the wrong element or text doesn't land in a focused
  field, call `resize_window` with `preset: "desktop"` first, then
  re-verify focus/state via `javascript_exec` (e.g. checking
  `document.activeElement.tagName` or reading `aria-checked` on toggle
  switches) rather than trusting a screenshot alone.
- **No fabricated data, ever** — this norm blocked several tempting
  shortcuts this session (the eval set, voice-cloning reference clips)
  and should keep blocking them. When real data doesn't exist, build the
  plumbing and leave it empty with clear instructions, don't invent
  placeholder content.

## 5. Quick file map for what changed this session

- `voxdirector/config.py` — most new tunable constants live here
  (`ALPHA_WINDOW_CHARS`, `BETA_CHUNK_CHARS`, `GAMMA_*`, `DB_PATH`), each
  commented as first-pass/tunable.
- `voxdirector/text_utils.py` (new) — shared windowing/normalize/filter
  helpers used by Alpha, Beta, and `backend/app/main.py`.
- `voxdirector/voice_scoring.py` (new) — Phase 2 voice selection.
- `voxdirector/db.py` (new) — Phase 1 SQLite trace log.
- `voxdirector/agents/alpha_ingestion.py` — map-reduce windowing,
  richer tags, fuzzy rescue, and the new coverage-gap fix.
- `voxdirector/agents/beta_consistency.py` — chunking, diff computation,
  fresh-per-call emotion lexicon loading (Fix #1 above).
- `voxdirector/agents/gamma_qa.py` — per-word confidence, recalibrated
  flagging.
- `voxdirector/orchestrator.py` — retry-and-pick-best, refactored
  `rerender_chunk()`.
- `backend/app/main.py` — wiring for all of the above, settings cache
  invalidation.
- `frontend/src/components/DiffView.tsx` (new), `ProgressStages.tsx`
  (spinner), `ResultView.tsx`, `GenreVoiceSuggestion.tsx`,
  `frontend/src/lib/types.ts` — UI surfacing for everything above.
- `data/eval_set/` (new), `scripts/run_eval.py` (new) — still empty,
  see section 3.
