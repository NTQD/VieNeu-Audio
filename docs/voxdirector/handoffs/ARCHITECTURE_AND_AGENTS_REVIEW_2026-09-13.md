# VoxDirector AI — Architecture Review & Agent Roadmap (2026-09-13)

Prepared as a structural review: CPU/GPU parallel development strategy, an
audited status report on Alpha/Beta/Gamma (grounded in the actual current
code, not the original spec's assumptions), and a master plan to bring the
3-agent system toward its full potential.

---

## Part 1: CPU & GPU Parallel Architecture Strategy

**Confirmed understanding:** one codebase, two runtime tracks, updated
together in lockstep — no more manually zipping and hand-carrying files to a
separate machine.

### What's already in place
- `backend/Dockerfile` (CPU, VPS-primary) and `backend/Dockerfile.gpu`
  (CUDA 12.8, local-hardware-optimized) as **parallel files in the same
  tree**, not parallel branches.
- `backend/requirements.txt` / `backend/requirements-gpu.txt` — identical
  except `vieneu==3.6.4` vs `vieneu[cuda]==3.6.4`.
- `docker-compose.yml` (always used) + `docker-compose.gpu.yml` (additive
  override via `-f`) — GPU reservation and Whisper-on-CPU-by-VRAM-budget
  live only in the override, nothing is duplicated.
- Env-var-driven behavior switches already exist (`VOXDIRECTOR_WHISPER_DEVICE`,
  `EXPECTED_VIENEU_VERSION`) — the right pattern to keep extending rather
  than branching code paths.

**Why branches are the wrong tool here:** a long-lived `cpu` branch and
`gpu` branch inevitably drift — every agent/frontend fix has to be
cherry-picked twice, which is exactly the workflow you said is no longer
viable. One branch, parallel config files selected by which command you
run, is what actually lets both tracks update simultaneously by
construction (one commit, one `git pull`, both tracks current).

### The actual blocker to "no more zip files" — must fix first
`git remote -v` shows `origin` pointing at `pnnbao97/VieNeu-TTS` — the
**upstream open-source SDK repo**, not a repo you control. Meanwhile, the
entire VoxDirector layer (`frontend/`, `backend/`, `voxdirector/`,
`pipeline/`, `data/`, weeks of work) exists only as **uncommitted files on
local disk** — there is no commit history for any of it on the branch
currently checked out, and nothing has ever been pushed anywhere. A GPU
machine literally cannot `git pull` something that was never pushed.

**Required one-time setup (needs your action, not just mine):**
1. Create a private repo you own (GitHub/GitLab/etc.).
2. I add it as a second remote (e.g. `origin` stays upstream for pulling
   SDK updates, `vox` points at your new repo) and commit the current
   working tree to a real branch.
3. Push. From then on: GPU machine runs `git pull`, checks out the same
   branch, runs `docker compose -f docker-compose.yml -f
   docker-compose.gpu.yml up --build -d`. CPU/VPS machine does the same
   without the `-f docker-compose.gpu.yml` part. Same commit, two runtimes.

I have not created or pushed anything — this needs your go-ahead since it
means picking/creating a real external repo.

### Convenience layer (recommended, small effort)
- A `Makefile` (or `justfile`) with `make cpu-up` / `make gpu-up` / `make
  cpu-build` / `make gpu-build` so nobody has to remember the `-f` chain.
- Optional: a GitHub Actions workflow that runs `docker compose build`
  (CPU only — GPU runners are expensive/impractical for a student-budget
  CI) on every push, so a change that breaks the CPU/VPS track is caught
  immediately even while you're focused on GPU work. GPU correctness stays
  a manual check on the actual GPU machine, same as today.

---

## Part 2: Agents Status Report & Roadmap

Audited against the original build spec (`VoxDirectorAI_Technical_Spec.md`,
Section 6) and the actual current source — not estimated from memory.

### Agent Alpha — Ingestion, Voice-Suggestion & Flagging — **~85% complete**

**Operational:** Yes, in production use, all 4 intended responsibilities
implemented and verified live: chapter segmentation (with/without explicit
headings), genre detection + code-computed voice mapping (LLM never
invents a voice ID), emotion-segment flagging, pause-point flagging.
Anti-hallucination quote-verification is real (`_filter_hallucinated_quotes`
strips any flagged quote that doesn't actually appear in the source text).

**Gaps to 100%:**
- `needs_review` is computed correctly (confidence-threshold enforced in
  code, not just trusted from the LLM) but **zero frontend references
  exist** — a chapter boundary the system itself flagged as uncertain is
  silently invisible to the user. *(Effort: small — add a badge to the
  chapter/segment list.)*
- Genre taxonomy is only 4 buckets (`kiem_hiep`/`ngon_tinh`/`trinh_tham`/
  `khac`, the last added this week specifically to stop forced
  misclassification). `khac` fixed the *distortion* problem but every
  "khac" text still gets the same one default voice regardless of its real
  character. *(Effort: medium — richer tagging, see Part 3.)*
- Single-call-for-the-whole-book design has no upper bound testing —
  works for every chapter-length text tested so far, but has never been
  stress-tested on a genuinely long novel (50k+ words) to confirm chapter-
  boundary accuracy holds up at that input size. *(Effort: medium — needs
  a real long-text test, then likely the map-reduce restructure in Part 3.)*
- The spec's own KPI section (chapter/emotion/pause match-rate targets)
  was written for Piper and has never been re-measured for VieNeu — we
  have no actual accuracy number, only "seems to work in manual testing."

### Agent Beta — Consistency & Expression — **~65% complete**

**Operational:** Partially. The single-call, three-pass design (terminology
+ expression + pause-sentinel) works and is wired end-to-end. A real
production bug was already caught and fixed here (Gemini assigning a
free-text `entity_type` that didn't match the system's enum — now a hard
Pydantic `Literal`).

**Gaps to 100% — two of these are more serious than "incomplete," they are
dead code paths:**
- 🔴 **`approve_new_entries()` is never called from anywhere.** The
  frontend's "Duyệt" (Approve) button on a new glossary term only removes
  it from the on-screen notification list (`setNewTerms(prev => prev.filter(...))`)
  — it never calls any backend endpoint, so **the glossary can never
  actually grow through the UI**. This is the core self-improving-
  consistency loop the whole RAG-glossary design depends on, and it does
  not work today. *(Priority: fix before anything else in Beta — this is
  a P0, not a roadmap item.)*
- 🔴 **`expression_report` and `pause_report`** — Beta computes a detailed
  per-attempt match/skip diagnosis for every emotion word and pause
  sentinel it tries to insert, and `orchestrator.py` **discards both
  fields** the moment `run_beta()` returns. Nobody — not you, not a future
  debugging session — can currently see *why* an expected emotion word
  didn't get inserted.
- The emotion lexicon shrank from an originally-envisioned richer set down
  to exactly 3 tags (`[cười]`, `[thở dài]`, `[hắng giọng]`) after
  confirming VieNeu-TTS only genuinely supports those 3 experimental
  bracket tags. This is a real capability ceiling inherited from the
  engine swap, not a Beta bug — but it means Beta's "expression insertion"
  pass is currently much narrower than originally designed.
- Same long-chapter truncation exposure as Alpha (mitigated by the
  max-output-tokens fix, not eliminated for a genuinely oversized single
  chapter).
- No diff view anywhere — users have no way to see what Beta actually
  changed in a chapter's text (terminology corrections, inserted words),
  only the final synthesized audio.

### Agent Gamma — QA Agent — **~80% complete**

**Operational:** Yes. Code-computed WER (never LLM-estimated, correctly
matches the anti-hallucination principle), per-chunk flagging, on/off
toggle fully wired (frontend → WS → orchestrator), CPU/GPU device
selectable independently of the TTS engine. This session's timing
instrumentation also confirmed it correctly measures real ASR cost.

**Gaps to 100%:**
- `summarize_qa_report()` is fully implemented (optional Gemini narrative
  summary of the QA numbers) and **never called** — dead code. The result
  view only ever shows the raw WER percentage.
- Purely reactive: Gamma *reports* a bad segment, nothing *acts* on it — a
  flagged segment still requires a human to notice the red badge and
  manually click "Render lại." No auto-retry exists.
- The flag threshold (`max(overall_wer * 1.5, WER_PASS_THRESHOLD)`) is a
  reasonable-sounding heuristic that has never been calibrated against
  real human judgment of "was this segment actually bad."
- faster-whisper returns per-word confidence and timestamps; none of that
  is used today — flagging is whole-chunk-WER-only, which can't localize
  *which word* is suspect.

---

## Part 3: Expert Consultation — Peak Agent Performance

### The pattern underneath all three findings above

Every gap I found in Part 2 that isn't a genre-taxonomy or lexicon-breadth
limitation is the **same architectural failure mode repeated three times**:
**the agents already compute richer, more useful output than the product
surfaces.** Alpha's `needs_review`, Beta's `expression_report`/
`pause_report`, Gamma's `summarize_qa_report` — all real, all computed, all
silently dropped between the agent and the human. This is the highest-
leverage fix available: not "make the agents smarter," but "stop throwing
away the intelligence they already produce." I'd sequence the master plan
around closing this pattern first, then layering genuinely new capability
on top.

### Master plan

**Phase 0 — Stop the leaks (do this before anything below — days, not weeks)**
1. Wire `approve_new_entries()` to a real `POST /api/glossary/approve`
   endpoint, called from `NewTermConfirmationPanel`'s "Duyệt" action.
   Without this, every other Beta improvement below is built on a
   glossary that can never actually grow.
2. Surface `expression_report`/`pause_report` in the segment list (a small
   "🗨️ chèn 'thở dài'" / "⊘ bỏ qua: không khớp" annotation per segment).
3. Surface `needs_review` as a badge on flagged chapters/segments.
4. Either wire `summarize_qa_report()` into the QA result panel, or delete
   it — a spec-mandated feature sitting unused is worse than not having
   promised it.

**Phase 1 — Persistence & measurement (turns "I think it works" into a number)**
5. Every job currently lives only in an in-memory Python dict
   (`JOBS: dict[str, dict]`) — gone on restart, and impossible to analyze
   after the fact. Add a lightweight SQLite-backed job/trace log (no new
   infrastructure, no new ops burden appropriate for this project's scale)
   recording each agent's input/output/confidence/timing per job. This is
   also what finally makes the timing-breakdown work from this session
   *historical* instead of one-off.
6. Build a small real eval set (10-20 chapters spanning your 3 genres +
   "khác") with human-graded expected chapter boundaries, expected
   emotion/pause matches, and known-good transcripts. Run it after every
   agent-prompt change. This operationalizes the original spec's KPI
   section, which has never actually been measured for VieNeu.

**Phase 2 — Alpha: scale and precision**
7. **Map-reduce restructure for long novels**: instead of one call over
   the entire `raw_text`, split into overlapping windows, run Alpha per
   window, reconcile chapter boundaries at window seams and take a
   majority/weighted vote on overall genre across windows. Removes the
   single-call ceiling entirely rather than just raising it (which is all
   the max-output-tokens fix did).
8. **Richer genre signal**: instead of one flat genre bucket driving one
   voice, have Alpha emit secondary tags (tone: dark/light, pacing:
   fast/slow, target audience) and drive voice selection off a small
   scoring function across all 23 real voices' region/style metadata —
   turns "khác → always the same default voice" into an actual
   recommendation.
9. **Recover near-miss quotes**: the current hallucination filter is exact
   (post-whitespace-normalization) string matching — a semantically valid
   but slightly paraphrased quote gets silently dropped. A cheap fuzzy-
   match fallback (e.g. token-overlap ratio above a threshold) before
   discarding would recover legitimate flags currently being thrown away.

**Phase 3 — Beta: expressiveness ceiling**
10. Investigate VieNeu's own "instant voice cloning" capability (it's in
    the SDK's own PyPI description) as a **richer alternative to bracket
    tags** — if VieNeu can take a short reference clip to color delivery,
    Beta could recommend/attach an emotional reference sample for a
    flagged segment instead of being capped at 3 words. This is the
    single highest-ceiling improvement available for Beta, because it
    sidesteps the "only 3 supported tags" wall entirely rather than
    working around it.
11. Chunk oversized chapters before Beta the same way as Alpha's map-
    reduce, sharing glossary context across sub-chunks.
12. Add a chapter-level diff view (raw vs. corrected_text) in the UI —
    pure transparency, no model change needed, closes a real trust gap.

**Phase 4 — Gamma: from reporter to corrector**
13. **Automatic retry-and-pick-best**: when a segment's WER exceeds the
    flag cutoff, automatically re-synthesize it (VieNeu is stochastic —
    we already have direct evidence from this session that a second
    synthesis of the same text can come out cleaner) up to N times and
    keep the best-scoring take, *before* ever showing it to the user. This
    directly targets the "misreading" issue we investigated last session,
    turning a manual "Render lại" chore into an automatic fix.
14. Use faster-whisper's per-word confidence/timestamps (already computed,
    currently discarded) to localize *which word* is suspect, not just
    flag the whole chunk — much more actionable for both auto-retry and
    human review.
15. Calibrate the flag-cutoff heuristic against the Phase 1 eval set
    instead of the current unvalidated `1.5x` multiplier.
16. Extend QA scope cheaply with code-only audio-health checks (clipping,
    unexpected silence, level normalization) alongside WER — no LLM cost,
    meaningfully more "quality assurance" than transcript-matching alone.

**Cross-cutting, do opportunistically:**
17. Model resilience — `GEMINI_MODEL` is a single hardcoded pin with no
    fallback; this project has already hit one hard model deprecation
    (`gemini-2.5-flash` → 404) mid-build. A configurable fallback model,
    checked at startup/between jobs (never mid-pipeline, preserving the
    spec's "one model per run" reproducibility rule), would prevent the
    next deprecation from being a fire drill.
18. Lightweight BYOK cost/token estimate per job — cheap to add now that
    Alpha/Beta can each consume up to 65,536 output tokens, and directly
    useful to users bringing their own free-tier quota.

---

**My recommendation on sequencing:** Phase 0 first, unconditionally — it's
small, fast, and every later improvement to Beta specifically is wasted
effort while the glossary-growth loop is silently broken. Phase 1 second,
because "master plan" items in Phase 2-4 are unverifiable without it. Phase
2-4 in whatever order matches which agent's quality is most visibly
bothering you day to day.
