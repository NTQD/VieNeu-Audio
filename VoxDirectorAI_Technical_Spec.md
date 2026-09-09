# VoxDirector AI — Technical Specification for Implementation

**Document purpose:** This is an engineering handoff spec for an AI coding agent (Claude Code) to implement the VoxDirector AI upgrade on top of the existing VieNeu-Audio repository. It defines exactly what to build, what NOT to touch, data contracts between components, and acceptance criteria.

**Project:** Upgrade VieNeu-Audio (a working, rule-based Vietnamese audiobook production pipeline) into a Multi-Agent system by inserting an AI Orchestration Layer of 4 LLM-driven Agents (codenamed **Alpha, Beta, Gamma, Delta**) between existing pipeline stages.

**Base repository:** `github.com/NTQD/VieNeu-Audio`
**LLM provider:** Google Gemini API (Flash tier), called from Python, deployed on Google Cloud Run
**Orchestration framework:** LangGraph
**Vector store:** ChromaDB (for the Character/Terminology Glossary used by Agent Beta)
**ASR (for QA):** faster-whisper (local, open-source, no API cost)

---

## 1. Golden Rule — Read This First

**Do not modify the internal logic of the existing pipeline modules.** They are in production and stable. The 4 new Agents are inserted _around_ these modules, calling them as-is. If a new Agent needs a new capability from an existing module (e.g. a new parameter), extend the module minimally and additively — never rewrite its core logic.

Before writing any integration code, **inspect the actual current source** of each file listed in Section 2 to confirm exact function signatures — the descriptions below are based on the project's README and prior design discussion, not a byte-for-byte read of the current source. Treat function names/signatures below as the intended contract; verify and adjust against the real file before wiring calls.

---

## 2. Existing System — What Already Works (Do Not Rewrite)

| File                                                         | Responsibility                                                                                                                                                                                                                                                                    |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `text_normalizer.py`                                         | Normalizes raw Vietnamese text — numbers, units, symbols — into spoken-word form.                                                                                                                                                                                                 |
| `text_splitter.py`                                           | Splits normalized text into ~250-word, sentence-aligned chunks sized for the TTS engine.                                                                                                                                                                                          |
| `auto_tts.py`                                                | Gradio orchestration app. Handles voice selection/cloning, batch rendering, chapter detection via `Chương N` regex heading match, skip-already-rendered logic, health-check. **Currently accepts `.txt` file drop only — see Section 4 for the required extension.**              |
| `audio_postprocess.py`                                       | FFmpeg-based audio concatenation, configurable silence insertion between paragraphs/chapters, background music mixing.                                                                                                                                                            |
| `subtitle_generator.py`                                      | Generates `.srt` subtitles using character-count-weighted timing (not forced alignment).                                                                                                                                                                                          |
| `video_renderer.py`                                          | FFmpeg video rendering; auto-detects available H.264 encoder (NVENC / QuickSync / libx264).                                                                                                                                                                                       |
| `make_video.py`                                              | CLI entry point that runs the post-production chain (audio → subtitle → video) standalone.                                                                                                                                                                                        |
| VieNeu-TTS (third-party, installed via `pip install vieneu`) | The actual voice synthesis engine. Supports voice cloning, emotion cues (e.g. `[cười]`, `[thở dài]`), and a multi-speaker "Conversation" mode. **The current pipeline does not yet make use of emotion cues or multi-speaker mode** — this is one of the gaps Agent Gamma closes. |

**Known limitation explicitly acknowledged in the existing README:** chapter detection relies on a `Chương N` heading regex; text without that heading pattern falls back to generic naming. Agent Alpha exists specifically to fix this.

---

## 3. Target Architecture

```
┌───────────────────────────────────────────────────────────┐
│  auto_tts.py (Gradio UI — EXISTING, extend per Section 4)    │
│  - Voice selection / cloning (existing)                      │
│  - Voice audition / test-read (existing)                     │
│  - Input: .txt drop (existing) + .docx drop (NEW — Section 4) │
└──────────────────────────┬────────────────────────────────┘
                           ▼
┌───────────────────────────────────────────────────────────┐
│  NEW: AI ORCHESTRATION LAYER (LangGraph)                     │
│                                                               │
│  raw_text                                                     │
│     │                                                          │
│     ▼                                                          │
│  ① Alpha  — Ingestion Agent (LLM)                             │
│     → segments raw text into chapters                         │
│     │                                                          │
│     ▼                                                          │
│  ② Beta   — Consistency Agent (LLM + RAG/ChromaDB)             │
│     → enforces glossary-consistent terminology per chapter     │
│     │                                                          │
│     ▼                                                          │
│  [EXISTING] text_normalizer.py → text_splitter.py              │
│     │                                                          │
│     ▼                                                          │
│  ③ Gamma  — Prosody Agent (LLM)                                │
│     → tags narration/dialogue, speaker_id, emotion_tag          │
│     │                                                          │
│     ▼                                                          │
│  [EXISTING] VieNeu-TTS engine (consumes Gamma's tags)           │
│     │                                                          │
│     ▼                                                          │
│  [EXISTING] audio_postprocess.py → subtitle_generator.py        │
│              → video_renderer.py                                │
│     │                                                          │
│     ▼                                                          │
│  ④ Delta  — QA Agent (faster-whisper ASR round-trip)            │
│     → computes Word Error Rate, flags suspect segments           │
└───────────────────────────────────────────────────────────┘
                           ▼
                 Output: .mp4 + .srt + qa_report.json
```

---

## 4. Task: Extend `auto_tts.py` for `.docx` Input

**Current state:** accepts `.txt` file drop only.
**Required:** also accept `.docx` file drop, extract plain text, and feed it into the exact same downstream code path that `.txt` currently uses (i.e. do not create a parallel pipeline — converge to the same `raw_text: str` variable as early as possible).

**Implementation guidance:**

- Add `python-docx` to `requirements.txt`.
- Add a small file-type dispatch: if the uploaded file extension is `.docx`, use `docx.Document(path)` and join all non-empty paragraph `.text` values with `\n` to produce the raw text string; if `.txt`, keep existing read logic unchanged.
- Do not attempt to preserve `.docx` formatting (bold, italics, headings-as-styles) — plain text extraction only. Chapter structure is handled downstream by Agent Alpha, not by Word heading styles.
- Add a unit test with a sample `.docx` file containing at least 2 "chapters" with no explicit `Chương N` text, to later validate Agent Alpha's semantic chapter detection (Section 6.1).

---

## 5. New Directory Structure

```
voxdirector/
├── agents/
│   ├── __init__.py
│   ├── state.py              # Shared LangGraph state schema
│   ├── alpha_ingestion.py
│   ├── beta_consistency.py
│   ├── gamma_prosody.py
│   └── delta_qa.py
├── glossary/
│   ├── __init__.py
│   ├── schema.py              # Pydantic models for glossary entries
│   └── store.py                # ChromaDB setup + retrieval helpers
├── graph.py                    # LangGraph wiring — connects Alpha→Beta→[existing]→Gamma→[existing]→Delta
├── llm_client.py                # Gemini API client wrapper (single place to swap models/keys)
└── config.py                    # CONFIDENCE_THRESHOLD, model names, etc.
```

---

## 6. Agent Specifications

### 6.0 Shared Conventions (apply to all 4 agents)

- **LLM provider:** Google Gemini API. Use the official `google-genai` Python SDK. Centralize the client instantiation in `llm_client.py` so the model name/provider can be swapped in one place later if needed.
- **Output format:** All agents return **structured JSON only** — no prose, no markdown fences around the JSON, no explanatory text outside the JSON object unless a field is explicitly designated for that purpose. Use Gemini's structured output / JSON mode rather than asking the model to "please return JSON" in free text.
- **Confidence handling:** Any field that involves the model's judgment (not a deterministic transformation) MUST include a `confidence_score` float in `[0.0, 1.0]`.
- **Confidence threshold: `CONFIDENCE_THRESHOLD = 0.75`** (define once in `config.py`, import everywhere — do not hardcode in multiple files). Below threshold: the agent still returns its best-guess value but the caller must treat it as provisional (see per-agent fallback behavior below); do not block the pipeline on low confidence.
- **Field naming:** JSON keys in English (`snake_case`). String _values_ inside those fields remain in Vietnamese (the language of the source novel) — never translate or paraphrase user content.
- **No hallucination beyond scope:** every agent's system prompt below encodes a different degree of "permitted inference" appropriate to its task — see each agent's "Anti-hallucination rule" below. Implement exactly as specified; do not loosen these rules for convenience.

---

### 6.1 Agent Alpha — Ingestion Agent

**Purpose:** Segment raw input text into chapters, including cases with no explicit `Chương N` heading (fixes the acknowledged limitation of the existing pipeline).

**Input:** `raw_text: str` (from `.txt` or the new `.docx` path in `auto_tts.py`)

**Output schema:**

```json
{
  "chapters": [
    {
      "start_index": 0,
      "end_index": 1520,
      "confidence_score": 0.91,
      "needs_review": false
    }
  ]
}
```

**Anti-hallucination rule:** Alpha may infer chapter boundaries from semantic cues (time/place shifts, narrator perspective changes) when no explicit heading exists. Every boundary must carry `confidence_score`. If `confidence_score < CONFIDENCE_THRESHOLD`, still return the boundary but set `needs_review: true` — never silently assert a low-confidence boundary as certain. Alpha must never summarize, paraphrase, or alter the source text — only report index positions.

**Fallback behavior when below threshold:** Do not block. Downstream (Beta) still receives the chapter as segmented; the `needs_review` flag is surfaced in logs/UI for the Data & Domain Curator to review after the fact — pipeline continues regardless.

**System prompt (Vietnamese — use verbatim in code, this is the actual production prompt):**

```
Bạn là Alpha, một biên tập viên bản thảo kỳ cựu tại nhà xuất bản, nhiều năm
kinh nghiệm đọc và phân đoạn thảo tiểu thuyết dài kỳ trước khi in ấn. Bạn có
con mắt tinh tường nhận ra điểm chuyển chương ngay cả khi tác giả quên đánh
dấu, nhưng luôn thận trọng — không bao giờ khẳng định chắc nịch khi bản thân
còn phân vân.

VAI TRÒ: Nhận diện và phân tách ranh giới chương trong văn bản tiểu thuyết thô.

NĂNG LỰC: Bạn hiểu cấu trúc văn học tiểu thuyết (chuyển cảnh, thay đổi thời
gian/không gian, chuyển góc nhìn nhân vật kể chuyện) và quy ước trình bày
chương phổ biến trong tiểu thuyết mạng Trung Quốc dịch Việt.

NGUYÊN TẮC:
- Được phép suy đoán ranh giới chương dựa trên dấu hiệu ngữ nghĩa khi văn bản
  không có heading tường minh dạng "Chương N".
- Mỗi ranh giới đề xuất phải kèm confidence_score (0.0 đến 1.0).
- Nếu confidence_score dưới 0.75, vẫn trả về đề xuất nhưng bắt buộc gắn
  needs_review = true.
- Cấm tuyệt đối: không được tự bịa nội dung không có trong văn bản gốc, không
  tóm tắt, không diễn giải lại câu chữ dưới bất kỳ hình thức nào.

NHIỆM VỤ:
- Đọc toàn bộ văn bản thô được cung cấp trong một lượt xử lý.
- Xác định các vị trí (index) đánh dấu điểm bắt đầu của mỗi chương.
- Làm sạch văn bản: loại bỏ ký tự thừa, khoảng trắng bất thường, watermark
  hoặc quảng cáo lẫn trong bản crawl (nếu phát hiện).
- Trả về danh sách chương đã tách kèm confidence_score cho từng ranh giới.

TƯ DUY: đọc toàn bộ văn bản một lượt; quét tìm heading tường minh trước
("Chương N", "Chapter N"); nếu không tìm thấy, phân tích các dấu hiệu ngữ
nghĩa; với mỗi ranh giới nghi ngờ, tự đánh giá và gán confidence_score; tổng
hợp kết quả đúng theo JSON schema, không thêm hoặc bớt field.

PHONG CÁCH: Output là JSON thuần, không kèm giải thích văn xuôi. Tên field
tiếng Anh; giá trị text (nếu có) giữ nguyên tiếng Việt, không dịch/diễn giải.
```

**Integration point:** Called once per uploaded document, before any existing pipeline module runs. Its output list of chapters is what Beta iterates over.

---

### 6.2 Agent Beta — Consistency Agent (RAG)

**Purpose:** Keep character names, place names, and special terms consistent across a long novel using a retrieval-augmented glossary, directly solving the "Red Matt should never become 'Đỏ Mát'" problem.

**Input:** `chapter_text: str` (one chapter from Alpha's output) + `glossary_context: list[dict]` (retrieved from ChromaDB)

**Glossary schema** (`glossary/schema.py`):

```python
from pydantic import BaseModel
from typing import Literal, Optional

class GlossaryEntry(BaseModel):
    original_term: str
    entity_type: Literal["character", "place", "term"]
    canonical_form: str
    pronunciation_note: Optional[str] = None
    first_seen_chapter: int
```

**Output schema:**

```json
{
  "corrected_text": "...",
  "applied_terms": [{ "original": "Red Matt", "canonical_form": "Red Matt" }],
  "new_entry_candidates": [
    {
      "term": "Huyết Nguyệt Tông",
      "entity_type": "term",
      "confidence_score": 0.83
    }
  ]
}
```

**Anti-hallucination rule (strictest of all 4 agents):** Beta must NEVER invent a canonical form for a term already present in the glossary — it must use the stored `canonical_form` exactly. For genuinely new terms not yet in the glossary, Beta must NOT decide a standard spelling itself — it only proposes `new_entry_candidates` for human confirmation. Every decision must be traceable to a specific glossary entry; there is zero freeform inference permitted for terminology decisions.

**RAG mechanics:**

- Vector store: ChromaDB, persistent collection named `character_glossary`.
- Embedding: use a free local embedding model (e.g. `sentence-transformers/all-MiniLM-L6-v2` via `HuggingFaceEmbeddings`) — do not depend on a paid embedding API for this.
- Retrieval: before calling the LLM for a chapter, query the collection with the chapter text (or its key entities) for the top-k (suggest k=10) most relevant existing glossary entries, and inject them into the prompt as `glossary_context`.
- After processing, any `new_entry_candidates` approved by the Data Curator should be written back into the ChromaDB collection so subsequent chapters can retrieve them.

**System prompt (Vietnamese — verbatim):**

```
Bạn là Beta, biên tập viên phụ trách tính nhất quán thuật ngữ tại một nhà
xuất bản sách dịch lâu năm. Bạn từng chứng kiến nhiều bản dịch bị độc giả
phàn nàn vì tên nhân vật đổi cách viết giữa chừng, nên bạn cực kỳ nguyên tắc:
chỉ tin vào bảng thuật ngữ đã được xác nhận, không bao giờ tự "chế" cách viết
mới dù có tự tin đến đâu.

VAI TRÒ: Duy trì tính nhất quán của tên riêng, địa danh và thuật ngữ xuyên
suốt toàn bộ tác phẩm, sử dụng RAG để tra cứu Character Glossary đã tích luỹ.

NĂNG LỰC: Bạn hiểu nguyên tắc giữ nguyên/phiên âm tên riêng trong dịch thuật
Trung–Việt (ví dụ: tên phương Tây giữ nguyên dạng gốc, không phiên âm Hán
Việt). Dữ liệu bạn được phép dùng: Character Glossary truy xuất từ ChromaDB
tương ứng với chương đang xử lý — đây là NGUỒN DUY NHẤT được phép dùng để xác
định cách viết chuẩn.

NGUYÊN TẮC:
- Cấm tuyệt đối tự sáng tạo cách viết mới cho bất kỳ tên riêng/thuật ngữ nào
  đã tồn tại trong glossary — bắt buộc dùng đúng canonical_form đã lưu.
- Với thuật ngữ hoàn toàn mới (chưa có trong glossary): không được tự ý
  chuẩn hoá — chỉ trích xuất và đề xuất dưới dạng new_entry_candidate kèm
  confidence_score, chờ xác nhận từ con người.
- Mọi quyết định phải truy nguyên được về một nguồn dữ liệu cụ thể trong
  glossary, không có ngoại lệ.

NHIỆM VỤ:
- Nhận văn bản chương hiện tại cùng glossary context truy xuất từ RAG.
- Rà soát toàn bộ tên riêng, địa danh, thuật ngữ đặc thù xuất hiện trong văn
  bản.
- Áp dụng canonical_form đã có trong glossary cho các thuật ngữ đã biết.
- Phát hiện và đề xuất (không tự áp dụng) đối với thuật ngữ mới.

TƯ DUY: quét toàn bộ văn bản tìm mọi tên riêng/địa danh/thuật ngữ đặc thù;
với mỗi thuật ngữ, truy vấn xem đã có trong glossary_context chưa; nếu có,
thay thế/xác nhận theo canonical_form; nếu không có, chỉ đánh dấu ứng viên
mới; không suy diễn thêm ngoài phạm vi văn bản và glossary được cung cấp.

PHONG CÁCH: Output JSON, field tiếng Anh, giá trị text tiếng Việt giữ nguyên
gốc. Không thêm bình luận hay giải thích lý do.
```

**Integration point:** Runs per-chapter, after Alpha, before the existing `text_normalizer.py`. Beta's `corrected_text` becomes the input to `text_normalizer.py` — do not feed Alpha's raw chapter text directly into the normalizer, it must pass through Beta first.

---

### 6.3 Agent Gamma — Prosody Agent

**Purpose:** Classify narration vs. dialogue and tag emotion/speaker so VieNeu-TTS's existing (currently unused) emotion cues and multi-speaker mode can be exploited.

**Input:** normalized/split text chunk (output of the existing `text_splitter.py`, which itself runs on Beta's corrected text)

**Output schema:**

```json
{
  "segments": [
    {
      "text": "...",
      "segment_type": "narration",
      "speaker_id": null,
      "emotion_tag": null,
      "confidence_score": 0.95
    },
    {
      "text": "...",
      "segment_type": "dialogue",
      "speaker_id": "character_a",
      "emotion_tag": "cuoi",
      "confidence_score": 0.88
    }
  ]
}
```

**Anti-hallucination rule (strictest "prefer null" policy):** Gamma may infer speaker and emotion from context, punctuation, and reporting verbs (e.g. "cô cười nói"). Every tag requires `confidence_score`. If below `CONFIDENCE_THRESHOLD`, the corresponding field (`speaker_id` and/or `emotion_tag`) must be `null` rather than a guessed value — a neutral read is always preferable to a wrong emotional read. Gamma must never invent dialogue or plot content not present in the source text.

**Fallback behavior:** `null` emotion_tag / speaker_id simply means VieNeu-TTS renders that segment with the default/narration voice and neutral tone — this is a safe, always-valid fallback, not an error state.

**System prompt (Vietnamese — verbatim):**

```
Bạn là Gamma, đạo diễn lồng tiếng dày dạn kinh nghiệm chỉ đạo diễn xuất cho
audiobook và phim hoạt hình. Bạn tinh tế trong việc đọc vị cảm xúc nhân vật
qua câu chữ, nhưng luôn tôn trọng nguyên tác — không bao giờ "diễn" thêm cảm
xúc mà văn bản gốc không thể hiện rõ.

VAI TRÒ: Phân tích văn bản để chỉ đạo diễn xuất giọng đọc — phân loại lời
thoại/lời dẫn truyện và gán nhãn cảm xúc phù hợp cho từng đoạn.

NĂNG LỰC: Bạn biết các emotion cue và chế độ multi-speaker mà VieNeu-TTS hỗ
trợ — danh sách tag hợp lệ được cung cấp kèm theo mỗi lần gọi.

NGUYÊN TẮC:
- Được phép suy đoán loại người nói (narration/dialogue) và cảm xúc dựa trên
  ngữ cảnh, dấu câu, động từ tường thuật.
- Mỗi nhãn gán phải kèm confidence_score. Nếu dưới ngưỡng 0.75, để trống
  (null) nhãn emotion thay vì đoán đại.
- Cấm tuyệt đối: không được tự thêm lời thoại hoặc tình tiết không có trong
  văn bản gốc.

NHIỆM VỤ:
- Chia văn bản thành các đoạn nhỏ theo lời dẫn truyện và lời thoại từng nhân
  vật.
- Gán speaker_id cho mỗi đoạn thoại dựa vào tên nhân vật trong ngữ cảnh gần
  nhất.
- Gán emotion_tag phù hợp trong danh sách tag hợp lệ được cung cấp.
- Giữ nguyên nội dung văn bản gốc, chỉ thêm nhãn.

TƯ DUY: đọc đoạn văn theo thứ tự; xác định ranh giới lời dẫn/lời thoại qua
dấu ngoặc kép và động từ tường thuật; với mỗi đoạn thoại, truy ngược ngữ cảnh
gần nhất để xác định speaker; đánh giá tín hiệu cảm xúc rõ ràng, không suy
diễn tâm lý sâu xa; gán confidence_score cho từng quyết định.

PHONG CÁCH: Output JSON, field tiếng Anh, giá trị text tiếng Việt. Ưu tiên
null hơn là đoán khi không chắc chắn — nguyên tắc "thà thiếu còn hơn sai" áp
dụng nghiêm ngặt nhất ở Agent này.
```

**Integration point:** Runs after `text_splitter.py`, before the VieNeu-TTS call. Gamma's tagged segments become the actual input payload to VieNeu-TTS's synthesis call (mapping `emotion_tag` → VieNeu-TTS emotion cue syntax, `speaker_id` → VieNeu-TTS multi-speaker voice selection). Confirm VieNeu-TTS's exact expected input format from its own API before wiring this mapping.

---

### 6.4 Agent Delta — QA Agent

**Purpose:** Objectively verify rendered audio quality via ASR round-trip, producing a measurable Word Error Rate.

**Input:** rendered audio file path (output of `audio_postprocess.py`) + the original source text for that chapter

**Output schema:**

```json
{
  "word_error_rate": 0.06,
  "flagged_segments": [
    {
      "segment_index": 14,
      "original_text": "...",
      "asr_transcript": "...",
      "deviation_score": 0.34
    }
  ]
}
```

**Anti-hallucination rule:** Delta must not speculate on _why_ an error occurred (e.g. "possibly a regional pronunciation issue") without evidence in the transcript diff. All reporting must be grounded in measured deviation between ASR transcript and source text — no subjective commentary.

**Implementation:**

```python
from faster_whisper import WhisperModel
import jiwer

model = WhisperModel("medium", device="cpu", compute_type="int8")

def verify_audio_quality(audio_path: str, original_text: str) -> dict:
    segments, _ = model.transcribe(audio_path, language="vi")
    transcript = " ".join(seg.text for seg in segments)
    wer = jiwer.wer(original_text, transcript)
    return {"word_error_rate": wer, "transcript": transcript, "passed": wer < 0.08}
```

Use the `medium` Whisper model size for final evaluation runs (better accuracy); a smaller/faster model may be used during iterative development to save time, but the number reported in the final KPI report must come from `medium` or larger.

**System prompt (Vietnamese — verbatim, used only for the segment-flagging/summary step, not for the WER computation itself which is pure code):**

```
Bạn là Delta, kiểm toán viên chất lượng âm thanh tỉ mỉ, làm việc theo phương
pháp luận rõ ràng và khách quan tuyệt đối. Bạn không đưa ra nhận định cảm
tính, chỉ trình bày sự thật dựa trên số liệu đo lường được, để con người là
người ra quyết định cuối cùng.

VAI TRÒ: Kiểm định chất lượng âm thanh đầu ra bằng phương pháp đối chiếu ASR
round-trip, đo lường độ chính xác bằng số liệu khách quan.

NGUYÊN TẮC:
- Không được tự suy diễn nguyên nhân lỗi nếu không có bằng chứng cụ thể
  trong transcript đối chiếu.
- Chỉ báo cáo dựa trên sai khác đo được — không phỏng đoán lý do nếu không
  kiểm chứng được bằng số liệu.
- Với đoạn nghi ngờ lỗi: confidence_score/deviation_score phải dựa trên độ
  lệch ký tự/từ đo được, không dựa trên cảm tính.

NHIỆM VỤ:
- Nhận transcript ASR và văn bản gốc tương ứng theo từng chương.
- Tính Word Error Rate tổng thể cho toàn chương.
- Xác định các đoạn có sai lệch cao bất thường so với mặt bằng chung của
  chương (flagged_segments).
- Tổng hợp báo cáo kèm số liệu cụ thể, chính xác.

PHONG CÁCH: Output JSON, field tiếng Anh, giá trị text tiếng Việt. Số liệu
chính xác đến hai chữ số thập phân.
```

**Integration point:** Runs after `video_renderer.py` (or in parallel once audio is finalized, before video render if you want to gate on QA — team's choice). Output `qa_report.json` is consumed by a human (QA & Documentation role), not by any downstream Agent.

---

## 7. LangGraph Wiring (`graph.py`)

**State schema** (`agents/state.py`):

```python
from typing import TypedDict, Optional

class VoxDirectorState(TypedDict):
    raw_text: str
    chapters: list[dict]              # Alpha output
    current_chapter_index: int
    glossary_context: list[dict]      # retrieved from ChromaDB for current chapter
    corrected_text: str               # Beta output
    normalized_text: str              # existing text_normalizer.py output
    split_chunks: list[str]           # existing text_splitter.py output
    tagged_segments: list[dict]       # Gamma output
    rendered_audio_path: str
    final_video_path: str
    qa_report: Optional[dict]         # Delta output
```

**Graph structure:** linear per-chapter pipeline — Alpha runs once on the full document to produce the chapter list; then for each chapter: Beta → [existing normalizer/splitter] → Gamma → [existing TTS/postprocess/subtitle/video] → Delta. Implement chapter iteration as a loop that invokes the graph once per chapter, or as a LangGraph subgraph — either is acceptable; prioritize whichever is simpler to debug within the timeline.

**Critical constraint:** Do not use any "auto model routing" or multi-provider failover mechanism for these calls. Every agent call in a given pipeline run must go to the same, explicitly pinned Gemini model. Non-deterministic model switching between calls would undermine the reproducibility that Agent Beta and the KPI evaluation (Section 8) depend on.

---

## 8. Acceptance Criteria (KPIs)

| Metric                             | Target                                      | How to measure                                                                                                                |
| ---------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Word Error Rate (Delta)            | < 8%                                        | `jiwer.wer()` on a held-out test set of at least 10 chapters                                                                  |
| Terminology consistency (Beta)     | > 95%                                       | Manual spot-check: pick 5 recurring named entities, verify identical `canonical_form` used across all chapters they appear in |
| Chapter detection accuracy (Alpha) | > 90%                                       | Compare against manually-labeled chapter boundaries on a test set of chapters with NO `Chương N` heading                      |
| Pipeline stability                 | No crashes over 20 consecutive chapters     | Batch run test                                                                                                                |
| Existing pipeline regression check | Old `.txt`-only path still works unmodified | Run the pre-upgrade pipeline path end-to-end, confirm output unchanged                                                        |

---

## 9. Environment / Dependencies to Add

```
google-genai
langgraph
langchain
chromadb
sentence-transformers
faster-whisper
jiwer
python-docx
```

Pin exact versions after first successful install in the target Cloud Run environment; do not assume version numbers here without testing, as these libraries update frequently.

---

## 10. Suggested Build Order (maps to the team's 4-week plan)

1. `agents/state.py`, `config.py`, `llm_client.py` — scaffolding, verify a single Gemini call works end-to-end.
2. `.docx` support in `auto_tts.py` (Section 4) — small, isolated, do first to unblock test data creation.
3. Agent Alpha — standalone, testable on raw text files with and without `Chương N` headings.
4. `glossary/schema.py`, `glossary/store.py` — ChromaDB setup, seed with a handful of manually-entered terms for testing.
5. Agent Beta — standalone, test with a term appearing in chapter 1 and chapter 5, confirm identical `canonical_form`.
6. Agent Gamma — standalone, test the JSON output maps correctly to whatever input format VieNeu-TTS's multi-speaker/emotion API actually expects (verify this against VieNeu-TTS's real interface before assuming the mapping is trivial).
7. Agent Delta — standalone, test WER calculation against a known-good and a deliberately corrupted audio sample to sanity-check the metric.
8. Wire everything via `graph.py`, run on 3–5 full test chapters end-to-end.
9. Run the full KPI evaluation (Section 8) on the complete test set, iterate on prompts based on failures.
10. Confirm the old `.txt`-only, no-Agent pipeline path still runs unmodified as a regression check before final submission.

```markdown
## 11. Deployment Workflow

**Important distinction:** Google AI Studio is _not_ the runtime environment for this application. It is only used once, up front, to obtain a Gemini API key. The actual application (Gradio UI + LangGraph agents + FFmpeg pipeline) is containerized and deployed directly to **Cloud Run**, which is the real hosting target.

### 11.1 High-Level Flow
```

Local development (this repo)
│
▼
Obtain Gemini API key from Google AI Studio (one-time setup)
│
▼
Write/maintain Dockerfile (custom — see 11.2, do not rely on buildpack auto-detect)
│
▼
Build container → push to Google Artifact Registry
│
▼
Deploy container to Cloud Run
│
▼
Cloud Run issues a public HTTPS URL (\*.run.app) — this is the demo/staging environment

````

### 11.2 Dockerfile Requirement — Custom, Not Auto-Buildpack

Cloud Run can auto-build from source (`gcloud run deploy --source .`) for pure-Python apps, but this project has **non-Python system dependencies** — FFmpeg (used by `audio_postprocess.py` and `video_renderer.py`) and the faster-whisper model files (used by Agent Delta). A hand-written Dockerfile is required to guarantee these are present in the container:

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "auto_tts.py"]
````

Verify the exact CMD/entrypoint against how `auto_tts.py` actually launches the Gradio server (host/port binding must respect Cloud Run's `$PORT` env var, not a hardcoded port).

### 11.3 Build & Deploy Commands

```bash
# One-time setup
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud artifacts repositories create voxdirector-repo --repository-format=docker --location=asia-southeast1

# Build and push the container
gcloud builds submit --tag asia-southeast1-docker.pkg.dev/PROJECT_ID/voxdirector-repo/app

# Deploy to Cloud Run
gcloud run deploy voxdirector-ai \
  --image asia-southeast1-docker.pkg.dev/PROJECT_ID/voxdirector-repo/app \
  --region asia-southeast1 \
  --memory 2Gi \
  --allow-unauthenticated
```

### 11.4 API Key Handling — Secret Manager, Never Hardcoded

The Gemini API key must never be committed to the repository (this project will be pushed to public GitHub). Store it in Secret Manager and reference it at deploy time:

```bash
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-

gcloud run deploy voxdirector-ai \
  --image asia-southeast1-docker.pkg.dev/PROJECT_ID/voxdirector-repo/app \
  --set-secrets=GEMINI_API_KEY=gemini-api-key:latest
```

`llm_client.py` should read `os.environ["GEMINI_API_KEY"]` — never a literal string.

### 11.5 Persistent Storage Note

Cloud Run instances are ephemeral by default. Two components need data to survive across container restarts:

- **ChromaDB glossary** (Agent Beta): for this project's scale, the simplest reliable approach is to build the glossary file locally during development/testing and bundle the resulting `.chroma` directory into the Docker image at build time, rather than relying on runtime writes persisting. If live updates to the glossary must persist across deployments, mount a Cloud Storage bucket via Cloud Run's GCS volume mount support instead.
- **faster-whisper model weights**: bundle the chosen model size into the Docker image at build time to avoid a slow re-download on every cold start.

### 11.6 Deploy Early, Not Once at the End

Do not wait until all 4 Agents are complete to attempt the first deployment. Deploy a minimal "skeleton" version to Cloud Run in Week 1 — an app that starts up, serves the Gradio UI, and successfully makes one Gemini API call — to validate the container, FFmpeg installation, and Secret Manager wiring early. Redeploy incrementally as each Agent is completed, so environment-specific failures (missing system packages, port binding, memory limits) surface while there is still time to fix them, rather than all at once near the submission deadline.

### 11.7 Custom Domain + PWA — Minimal Cloud Run Instance (Proof of Deployability)

**Purpose of this instance:** This deployment exists to demonstrate the project _can_ run on a custom domain as an installable PWA — it is not the primary demo environment. The primary demo runs locally (Section 11.6-alt, local-first) to leverage GPU speed and avoid cold-start/latency issues inherent to Cloud Run for this workload.

**Step 1 — Enable PWA in the existing Gradio app**

In `auto_tts.py`, change the launch call:

```python
demo.launch(pwa=True, favicon_path="./assets/voxdirector_icon.png")
```

This is the only code change required — Gradio generates the PWA manifest automatically. No manual service worker or manifest.json needed.

**Step 2 — Purchase a domain** (any registrar — Namecheap, Google Domains successor, PA Vietnam, etc.)

**Step 3 — Map the domain to the Cloud Run service**

```bash
gcloud beta run domain-mappings create \
  --service=voxdirector-ai \
  --domain=yourdomain.com \
  --region=asia-southeast1
```

This command outputs DNS records (CNAME or A/AAAA) — add them at the domain registrar's DNS settings. Propagation typically takes a few minutes to a few hours.

**Step 4 — Keep this instance minimal-cost**

This Cloud Run instance is only meant to prove deployability, not to serve the live demo:

- Do **not** set `--min-instances=1` permanently (avoid idle cost) — let it scale to zero by default.
- Only bump `--min-instances=1` briefly around the moment you want to show it live to Mentor/Giảng viên (e.g. the day before submission), then scale back to zero afterward.
- Accept that this instance may be slower (cold start) — that is expected and acceptable, since it is a deployability proof, not the performance-critical demo.

**Primary demo environment:** Local machine with GPU, running the full pipeline directly — this is what actually gets demonstrated live for quality/speed. The Cloud Run + custom domain + PWA setup is shown separately as evidence of production deployability.

```

```
