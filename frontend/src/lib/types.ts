// Kieu du lieu dung chung - khop voi schema tra ve tu backend (hien tai la
// STUB, xem backend/app/main.py). Se can dieu chinh khi backend that (Step 9,
// Section 11 cua spec) tra ve schema chinh xac tu Alpha/Beta/Gamma that.

export interface VoiceOption {
  id: string;
  display_name: string;
  gender: string;
  region?: string;
  style?: string;
}

export interface VoicePresets {
  voices: VoiceOption[];
  genre_to_voice: Record<string, string>;
}

export interface SubmitResponse {
  job_id: string;
  chapters: number;
  detected_genre: string;
  suggested_voice_id: string;
  genre_confidence_score: number;
  // Section 5c cua PHASE0_HANDOFF.md - so chuong Alpha danh dau ranh gioi
  // tach chuong khong chac chan, can nguoi dung xem lai.
  chapters_needing_review: number;
  // Phase 2 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Richer genre
  // signal") - null khi Alpha tat (xem process_submission_fallback trong
  // voxdirector/orchestrator.py).
  tone: string | null;
  pacing: string | null;
  target_audience: string | null;
}

export type ProcessingStageKey = "alpha" | "beta" | "tts" | "assemble" | "qa";

export interface ProgressMessage {
  type: "progress";
  stage: ProcessingStageKey;
  label: string;
  stage_index: number;
  total_stages: number;
}

export interface SegmentInfo {
  id: number;
  chapter: number;
  chunk_index_in_chapter: number;
  text: string;
  duration_s: number | null;
  flagged: boolean;
}

export interface NewTermCandidate {
  term: string;
  entity_type: string;
  confidence_score: number;
}

export interface QualitySummary {
  word_error_rate: number;
  passed: boolean;
  flagged_segments_count: number;
  // Section 5d cua PHASE0_HANDOFF.md - tuy chon (chi co khi QA bat), tu
  // summarize_qa_report() - vang mat khi QA tat (xem fallback trong
  // backend/app/main.py:ws_progress()).
  summary?: string;
}

// Section 5b cua PHASE0_HANDOFF.md - khop BetaOutput trong
// voxdirector/agents/beta_consistency.py. KHONG co truong vi tri/quoted_text
// rieng - Beta khong tra ve doan van goc kem theo, chi tra ve ket qua khop/
// khong khop cho tung muc Alpha da gan co (xem docstring ExpressionReportItem/
// PauseReportItem o backend).
export interface ExpressionReportItem {
  matched: boolean;
  emotion_label: string;
  inserted_word: string | null;
  skipped_reason: string | null;
}

export interface PauseReportItem {
  matched: boolean;
  skipped_reason: string | null;
}

// 2026-09-13 - phan bo thoi gian tung giai doan (giay), de tra loi cau hoi
// "GPU co that su nhanh hon khong" bang so lieu thuc te thay vi doan: alpha/
// beta la Gemini API (KHONG lien quan GPU), tts_s la CHI RIENG luc goi
// VieNeu-TTS suy luan (day moi la phan GPU thuc su tang toc).
export interface TimingBreakdown {
  alpha_s: number;
  beta_s: number;
  tts_s: number;
  assemble_s: number;
  video_s: number;
  qa_s: number;
}

export interface ResultMessage {
  type: "result";
  audio_url: string;
  subtitle_url: string;
  // null khi khong co anh nen duoc upload (2026-09-12) - dieu kien de nut
  // "Xuat Video" hoat dong la phai co anh nen, xem AdvancedOptions/ResultView.
  video_url: string | null;
  quality_summary: QualitySummary;
  segments: SegmentInfo[];
  new_term_candidates: NewTermCandidate[];
  expression_report: ExpressionReportItem[];
  pause_report: PauseReportItem[];
  // 2026-09-12 - thoi gian THAT (giay) toan bo pipeline mat de xu ly xong job
  // nay (Alpha + Beta/TTS/ghep/video/QA) - xem backend/app/main.py:ws_progress().
  processing_time_s: number;
  timing_breakdown: TimingBreakdown;
}

export interface ErrorMessage {
  type: "error";
  message: string;
}

export type WsMessage = ProgressMessage | ResultMessage | ErrorMessage;

export interface AdvancedOptionsState {
  backgroundImage: File | null;
  backgroundMusic: File | null;
  pauseDurationMs: number;
  burnSubtitles: boolean;
  qaEnabled: boolean;
  // Nut bat/tat tung Agent (2026-09-12, phan hoi nguoi dung: "nut bat tat
  // AGENTS thu cong"). Mac dinh true (giu hanh vi cu). Tat Alpha -> backend
  // dung regex thuan (khong Gemini) de tach chuong, khong co genre/emotion.
  // Tat Beta -> bo qua glossary/bieu cam/sentinel ngat dai, dung nguyen text.
  alphaEnabled: boolean;
  betaEnabled: boolean;
}
