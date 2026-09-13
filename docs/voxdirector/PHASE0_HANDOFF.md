# VoxDirector AI — Session Handoff: Phase 0 Ready to Start

**Written:** 2026-09-13, end of a long multi-session build (Piper→VieNeu
engine reversal, full UI redesign, GPU packaging, this architecture
review) — context window ran out before Phase 0 implementation could
start. This doc is written so a **fresh session with zero memory of any of
that** can pick up and implement Phase 0 immediately, correctly, without
re-deriving anything below from scratch.

**Read this file first, in full, before touching code.** It supersedes
nothing — `docs/voxdirector/ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md`
(same folder) has the full 5-phase master plan and the reasoning behind
it; this file exists to make **Phase 0 specifically** immediately
actionable with exact file/line references, since that's the user's
explicit next step.

---

## 1. What VoxDirector AI is

A full-stack web app, built **on top of** the open-source VieNeu-TTS SDK
(this whole repo — `src/`, `apps/`, `client/`, etc. — is VieNeu-TTS's own
codebase; VoxDirector is a layer added alongside it, not a fork of it).
VoxDirector turns raw Vietnamese web-novel chapter text into a narrated
audiobook (audio + subtitles + optional video), via 3 Gemini-powered
agents (Alpha → Beta → Gamma) feeding VieNeu-TTS for synthesis.

- **Frontend:** `frontend/` — Next.js 16, React 19, Tailwind v4,
  shadcn/ui on **Base UI** (not Radix — matters if pulling any more
  ElevenLabs UI components, which assume Radix and need adapting).
- **Backend:** `backend/` — FastAPI, one `JOBS` in-memory dict (no
  persistence yet — see Phase 1), WebSocket-driven progress.
- **Agents:** `voxdirector/agents/{alpha_ingestion,beta_consistency,gamma_qa}.py`
- **Orchestration:** `voxdirector/orchestrator.py` (wires Alpha→Beta→TTS→
  assemble→video→QA), `backend/app/main.py` (HTTP/WS endpoints).
- **TTS engine:** VieNeu-TTS v3 Turbo, PyPI package pinned exactly
  (`vieneu==3.6.4` CPU / `vieneu[cuda]==3.6.4` GPU) — **never** the local
  `src/vieneu/` in this same repo, which is a different, older
  architecture that will silently shadow the real package if the wrong
  venv is used. This bit the project once already; `EXPECTED_VIENEU_VERSION`
  in `voxdirector/config.py` + a startup check in `backend/app/main.py`
  guard against it recurring. Do not touch `src/vieneu/`.

## 2. Where the code actually lives now (as of this handoff)

**GitHub, branch `VoxDirector`:** https://github.com/NTQD/VieNeu-Audio/tree/VoxDirector
(`master` on that repo is untouched/unrelated — this is a separate branch).
Two git remotes exist locally: `origin` = upstream `pnnbao97/VieNeu-TTS`
(the SDK, pull-only, never push here), `vox` = the user's own repo above
(push work here). **Always work on the `VoxDirector` branch, always push to
`vox`, never to `origin`.**

Working flow going forward: edit → commit → `git push vox VoxDirector`.
Any other machine (VPS, GPU laptop) just does `git pull` on the same
branch — the zip-file workflow is retired.

**Local working copy:** `E:\tool audio\VieNeu-TTS` (Windows), a real git
checkout now on branch `VoxDirector`. There are also several Claude Code
**git worktrees** under `.claude/worktrees/` from past sessions — treat
the main checkout above as source of truth; a new worktree forked from an
old base commit will be **missing all of this work** and needs a full
resync from the main checkout (this has bitten past sessions — don't
assume a fresh worktree already has `frontend/`, `backend/`, etc.).

## 3. CPU/GPU parallel architecture (already built, both current)

One branch, parallel files, not parallel branches:
- `backend/Dockerfile` (CPU) / `backend/Dockerfile.gpu` (CUDA 12.8,
  matches the RTX 5050/Blackwell GPU this was validated against)
- `backend/requirements.txt` / `backend/requirements-gpu.txt` (differ only
  in `vieneu==3.6.4` vs `vieneu[cuda]==3.6.4`, GPU one relies on
  `torch==2.8.0`+cu128 pre-installed in the GPU Dockerfile before anything
  else, to avoid pip silently resolving a CPU-only or mismatched torch)
- `docker-compose.yml` (base, always used) + `docker-compose.gpu.yml`
  (additive override — GPU reservation + `VOXDIRECTOR_WHISPER_DEVICE=cpu`
  to protect the 8GB VRAM budget from Gamma/Whisper contention)
- `Makefile` (root — **shared with the unrelated upstream SDK's own
  Makefile targets, appended at the bottom, don't touch the existing
  ones**): `make cpu-up` / `make gpu-up` / `-down` / `-build` /
  `make vox-logs` / `make vox-ps`. Not yet execution-tested (`make` wasn't
  installed in the session that wrote it) — verify it actually runs on
  whichever machine picks this up.
- Docs: `docs/voxdirector/RUNNING.md` (CPU/normal), `RUNNING_GPU.md`
  (GPU-specific, Windows+Docker Desktop+WSL2 steps).

## 4. Real agent status (verified against actual code, not the original spec)

Full detail + all 5 phases in `ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md`.
Short version:

- **Alpha** (~85%) — chapter split + genre + emotion + pause flagging, all
  working. Gaps: `needs_review` computed but invisible to users; narrow
  4-bucket genre taxonomy; never stress-tested on a full-length novel.
- **Beta** (~65%) — terminology + expression + pause-sentinel insertion in
  one call, working. **Two dead-code bugs found, not just gaps** — see
  Phase 0 below.
- **Gamma** (~80%) — ASR/WER QA working end-to-end, toggle wired. One
  dead-code function (`summarize_qa_report`), purely reactive (no
  auto-retry on a flagged segment).

**The unifying finding:** all three agents compute richer output than the
product ever shows the user. That's Phase 0.

## 5. Phase 0 — exact implementation plan (start here)

Four independent fixes. Do them in any order; none blocks another.

### 5a. Wire `approve_new_entries()` — the P0, do this one first

**The bug:** `voxdirector/agents/beta_consistency.py:184` defines
`approve_new_entries(candidates, chapter_number=None)` — writes a
human-approved term into the persistent ChromaDB glossary (`voxdirector/glossary/store.py:add_entry`).
It is never called from anywhere in the codebase (confirmed via repo-wide
grep). The frontend's "Duyệt" (Approve) button in
`frontend/src/components/NewTermConfirmationPanel.tsx:36` calls an
`onApprove(term)` prop whose actual implementation, in
`frontend/src/app/page.tsx` (search for `onApprove=`), is:
```ts
onApprove={(term) => setNewTerms((prev) => prev.filter((c) => c.term !== term))}
```
— it only removes the term from the on-screen list. **Approving a term
today has zero effect on the glossary.** The whole point of the RAG
glossary (Beta gets more consistent over time as terms are approved) does
not work.

**What to build:**
1. `backend/app/main.py`: new `POST /api/glossary/approve` accepting the
   candidate object (`term`, `entity_type`, `confidence_score` — see
   `frontend/src/lib/types.ts`'s `NewTermCandidate`), calling
   `approve_new_entries([candidate_dict])` from `voxdirector.orchestrator`
   (re-export or import directly from `voxdirector.agents.beta_consistency`).
   Note: `approve_new_entries` doesn't need a `job_id` — it writes straight
   to the persistent glossary store, unrelated to any specific job.
2. `frontend/src/lib/api.ts`: add `approveNewTerm(candidate)` calling that
   endpoint.
3. `frontend/src/app/page.tsx`: `onApprove` handler calls the new API
   function first (await it, handle/log errors — don't let a failed
   approve silently look like it worked), *then* filters local state.

**Known simplification to make deliberately, not by accident:** the
current `NewTermCandidate` type has no `chapter_number` or
`canonical_form` field, and `all_new_terms` (built in
`backend/app/main.py`'s `ws_progress()`) flattens candidates across all
chapters, losing per-chapter origin. `approve_new_entries`'s
`chapter_number` param already defaults to `None` and
`canonical_form` defaults to the term itself — it's fine to approve
without threading chapter provenance through for this first pass. Extending
the schema to carry it is a nice-to-have, not required for Phase 0 to be
"done."

### 5b. Surface `expression_report` / `pause_report`

**The bug:** `beta_consistency.py`'s `run_beta()` returns these two fields
(per-attempt match/skip diagnostics for every emotion word and pause
sentinel Beta tried to insert) in its dict. `voxdirector/orchestrator.py`'s
`process_chapter()` (~line 161-182) destructures `beta_result` but only
keeps `corrected_text`, `applied_terms`, `new_entry_candidates` — both
report fields are read and thrown away.

**What to build:**
1. `orchestrator.py`: also pull `expression_report`/`pause_report` out of
   `beta_result` inside the `if beta_enabled:` branch (they don't exist
   when Beta is off — default to `[]` in the `else` branch, matching the
   existing pattern for `applied_terms`), add both to `process_chapter()`'s
   returned dict.
2. `backend/app/main.py`: aggregate across chapters (same pattern as the
   existing `all_new_terms` loop) into the final WS "result" payload.
3. **Design question to actually think through, not skip**: these reports
   are indexed by Alpha's *flagged segments* (a segment of prose), not by
   TTS *chunks* (what `SegmentList.tsx` renders one row per). They won't
   map 1:1. Simplest honest first cut: show them as a separate small
   "Beta hoạt động" panel (list of "chèn 'thở dài' tại: ..." / "bỏ qua:
   không khớp" lines) rather than trying to force each one onto a specific
   segment row that may not correspond to it.

### 5c. Surface `needs_review`

**The bug is bigger than "add a badge":** `alpha_ingestion.py`'s
`_clamp_and_sort()` computes `needs_review` correctly per chapter and it's
present in `run_alpha()`'s returned `chapters_out` list — but
`SubmitResponse` (`backend/app/main.py`, returned from `POST
/api/submit`) only ever sends `job_id`, `chapters` (a **count**, `int`),
`detected_genre`, `suggested_voice_id`, `genre_confidence_score`. **The
per-chapter `needs_review` flag never leaves the backend today** — this
isn't a missing UI element, the data isn't even in the response schema
yet.

**What to build:**
1. `backend/app/main.py`: extend `SubmitResponse` to include a
   `chapters_needing_review: int` (count) or a small list of chapter
   indices — either is fine, pick whichever is less churn given
   `alpha_result["chapters"]`'s existing shape.
2. `frontend/src/lib/types.ts`: extend `SubmitResponse` to match.
3. `frontend/src/components/GenreVoiceSuggestion.tsx` (where chapter count
   is already shown): add a small warning line/badge when the count is
   > 0, e.g. "⚠ 2 chương cần xem lại ranh giới."

### 5d. Wire or delete `summarize_qa_report()`

**The bug:** `voxdirector/agents/gamma_qa.py:116` defines
`summarize_qa_report(qa_report)` (optional Gemini narrative summary of
already-computed WER numbers) — never called from `backend/app/main.py`'s
QA block or anywhere else.

**Decide, don't leave it hanging:** either
- (a) call it after building `qa_report` in `ws_progress()`'s QA block,
  add the resulting string to the payload, show it in `ResultView.tsx`'s
  QA panel below the WER line — this is genuinely useful since raw WER%
  is not very human-readable — or
- (b) delete the function entirely if the team decides a narrative summary
  isn't worth the extra Gemini call latency.

Given it's optional and gracefully degrades with no API key (see the
function's own fallback branch), (a) is the recommended default unless
there's a reason not to spend the extra ~1-2s per QA'd job.

## 6. Working conventions this project has settled on (don't relitigate)

- **Vietnamese-first**: all UI copy, code comments explaining *why*
  (not what), and agent prompts are in Vietnamese. Keep that going.
- **No fabricated data, ever** — this project has a strong, repeated
  pattern of computing things for real (WER via actual ASR round-trip,
  waveform-envelope-turned-out-unwanted-but-was-real-RMS-not-random,
  timing via `time.monotonic()`) rather than approximating/faking. Extend
  that norm to Phase 0's UI additions — no placeholder numbers.
- **Test in the actual running app before calling something done** — this
  project has caught multiple real bugs (Base UI vs Radix `asChild`
  mismatch, the re-render-doesn't-update-final.wav bug, the waveform/gear
  click collision) purely by clicking through the built UI, not by code
  review alone. Docker Desktop on this Windows machine sometimes needs
  manually starting (`start "" "C:\Program Files\Docker\Docker\Docker
  Desktop.exe"` then poll `docker info` until ready) if it's not already
  running — this has happened mid-session before.
- **Sync discipline**: if working in a worktree, changes must be manually
  copied to the main checkout (and vice versa) — there's no automatic
  sync between them. Always confirm which directory is "source of truth"
  for a given file before editing.
- **Don't over-build**: this is a small, budget-conscious student project
  (~3 beta testers). Match effort to that scale — e.g. SQLite over a real
  database for Phase 1, no Kubernetes, no heavy new dependencies without
  a clear reason.
