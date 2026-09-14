"use client";

import { useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "cn";
import { Badge } from "@/components/ui/badge";
import SegmentList from "./SegmentList";
import AudioPlayerBar from "./AudioPlayerBar";
import BetaActivityPanel from "./BetaActivityPanel";
import DiffView from "./DiffView";
import type { GeminiUsageSummary, ResultMessage, TimingBreakdown } from "@/lib/types";
import { API_BASE_URL, rerenderSegment } from "@/lib/api";

interface Props {
  result: ResultMessage;
  qaEnabled: boolean;
  jobId: string;
}

function withCacheBust(url: string, bust: number) {
  return url.includes("?") ? `${url}&t=${bust}` : `${url}?t=${bust}`;
}

function formatProcessingTime(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins} phút ${secs}s`;
}

// 2026-09-13 - phan bo tung giai doan, CHI hien muc nao thuc su > 0 (vd. tat
// Beta thi khong hien "Beta 0.0s" gay roi). alpha_s/beta_s la Gemini API -
// KHONG lien quan GPU cua may; tts_s moi la phan VieNeu-TTS suy luan thuc
// su, dung de tra loi "GPU co duoc dung khong" bang so lieu that.
const TIMING_LABELS: Record<keyof TimingBreakdown, string> = {
  alpha_s: "Alpha (Gemini)",
  beta_s: "Beta (Gemini)",
  tts_s: "Giọng đọc (VieNeu-TTS)",
  assemble_s: "Ghép audio",
  video_s: "Dựng video",
  qa_s: "Gamma (ASR)",
};

function TimingBreakdownRow({ breakdown }: { breakdown: TimingBreakdown }) {
  const entries = (Object.keys(TIMING_LABELS) as (keyof TimingBreakdown)[])
    .map((key) => ({ label: TIMING_LABELS[key], value: breakdown[key] }))
    .filter((e) => e.value > 0.05);

  if (entries.length === 0) return null;

  return (
    <p className="text-xs text-muted-foreground font-mono">
      {entries.map((e) => `${e.label} ${e.value.toFixed(1)}s`).join(" · ")}
    </p>
  );
}

// Muc 18 cua master plan - so token Gemini THAT SU da dung cho job nay (do
// chinh Gemini API tra ve, xem backend/app/main.py::_pop_gemini_usage_summary()).
// estimated_cost_usd = null (chua cau hinh gia trong data/gemini_pricing.json,
// KHONG phai mien phi) hien "chưa cấu hình giá" thay vi $0.00 - tranh hieu
// nham 1 con so THIEU la 1 con so DUNG.
function GeminiUsageRow({ usage }: { usage: GeminiUsageSummary }) {
  const totalTokens = usage.gemini_prompt_tokens + usage.gemini_output_tokens;
  if (totalTokens === 0) return null;

  return (
    <p className="text-xs text-muted-foreground font-mono">
      Token Gemini: {usage.gemini_prompt_tokens.toLocaleString("vi-VN")} vào +{" "}
      {usage.gemini_output_tokens.toLocaleString("vi-VN")} ra —{" "}
      {usage.estimated_cost_usd !== null
        ? `~$${usage.estimated_cost_usd.toFixed(4)}`
        : "chưa cấu hình giá"}
    </p>
  );
}

// Man ket qua: player + quality summary (neu bat QA) + segment list + export
// buttons - Section 8.1.1 cua spec.
export default function ResultView({ result, qaEnabled, jobId }: Props) {
  // cacheBust doi moi sau moi lan re-render (Step 10) de <audio src> load
  // lai ban .wav vua ghi de, khong dung ban cache cu cua trinh duyet.
  const [cacheBust, setCacheBust] = useState(0);
  const [rerenderingId, setRerenderingId] = useState<number | null>(null);
  const [rerenderError, setRerenderError] = useState<string | null>(null);

  const audioSrcBase = result.audio_url.startsWith("http")
    ? result.audio_url
    : `${API_BASE_URL}${result.audio_url}`;
  const audioSrc = withCacheBust(audioSrcBase, cacheBust);

  const subtitleSrcBase = result.subtitle_url.startsWith("http")
    ? result.subtitle_url
    : `${API_BASE_URL}${result.subtitle_url}`;

  // null khi khong co anh nen duoc upload truoc luc xu ly (2026-09-12) -
  // dieu kien nguoi dung yeu cau: co anh nen -> nut "Xuat Video" la link that,
  // khong co anh -> giu disabled nhu truoc (chi co nut Xuat Audio).
  const videoSrc = result.video_url
    ? result.video_url.startsWith("http")
      ? result.video_url
      : `${API_BASE_URL}${result.video_url}`
    : null;

  async function handleRerender(segmentId: number) {
    setRerenderError(null);
    setRerenderingId(segmentId);
    try {
      await rerenderSegment(jobId, segmentId);
      setCacheBust(Date.now());
    } catch (err) {
      setRerenderError(err instanceof Error ? err.message : "Render lại thất bại");
    } finally {
      setRerenderingId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center justify-between mb-1">
          <p className="font-display text-sm font-medium">Bản xem trước</p>
          <span className="text-xs text-muted-foreground font-mono">
            Thời gian xử lý: {formatProcessingTime(result.processing_time_s)}
          </span>
        </div>
        <TimingBreakdownRow breakdown={result.timing_breakdown} />
        <GeminiUsageRow usage={result.gemini_usage} />
        <div className="mt-2">
          <AudioPlayerBar src={audioSrcBase} cacheBust={cacheBust} />
        </div>
      </div>

      {qaEnabled && (
        <div className="rounded-lg border p-3 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Kiểm tra chất lượng (Gamma)</span>
            <Badge
              className={cn(result.quality_summary.passed && "bg-jade/15 text-jade border-jade/30")}
              variant={result.quality_summary.passed ? "outline" : "destructive"}
            >
              {result.quality_summary.passed ? "ĐẠT" : "CHƯA ĐẠT"}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground font-mono">
            WER: {(result.quality_summary.word_error_rate * 100).toFixed(1)}% —{" "}
            {result.quality_summary.flagged_segments_count} đoạn bị đánh dấu nghi ngờ.
          </p>
          {!!result.quality_summary.auto_retry_summary?.segments_retried && (
            <p className="text-xs text-jade">
              Tự động thử lại {result.quality_summary.auto_retry_summary.segments_retried} đoạn, đã sửa
              được {result.quality_summary.auto_retry_summary.segments_fixed} đoạn.
            </p>
          )}
          {result.quality_summary.audio_health &&
            (result.quality_summary.audio_health.any_clipping ||
              result.quality_summary.audio_health.any_near_silent ||
              result.quality_summary.audio_health.total_internal_silence_gaps > 0) && (
              <p className="text-xs text-destructive">
                Cảnh báo âm thanh:{" "}
                {[
                  result.quality_summary.audio_health.any_clipping && "có đoạn bị vỡ tiếng (clipping)",
                  result.quality_summary.audio_health.any_near_silent && "có đoạn gần như im lặng hoàn toàn",
                  result.quality_summary.audio_health.total_internal_silence_gaps > 0 &&
                    `${result.quality_summary.audio_health.total_internal_silence_gaps} khoảng lặng bất thường giữa lời thoại`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            )}
          {result.quality_summary.summary && (
            <p className="text-xs text-muted-foreground">{result.quality_summary.summary}</p>
          )}
        </div>
      )}

      <BetaActivityPanel expressionReport={result.expression_report} pauseReport={result.pause_report} />

      <DiffView diffs={result.chapter_diffs} />

      <SegmentList
        segments={result.segments}
        onRerender={handleRerender}
        rerenderingId={rerenderingId}
      />
      {rerenderError && <p className="text-xs text-destructive">{rerenderError}</p>}

      <div className="flex gap-2">
        <a
          href={audioSrc}
          target="_blank"
          rel="noreferrer"
          className={cn(buttonVariants({ variant: "default" }))}
        >
          Xuất Audio
        </a>
        {videoSrc ? (
          <a
            href={videoSrc}
            target="_blank"
            rel="noreferrer"
            className={cn(buttonVariants({ variant: "outline" }))}
          >
            Xuất Video
          </a>
        ) : (
          <Button variant="outline" disabled title="Cần cung cấp ảnh nền (Tuỳ chọn nâng cao) trước khi xử lý">
            Xuất Video
          </Button>
        )}
        <a
          href={subtitleSrcBase}
          target="_blank"
          rel="noreferrer"
          className={cn(buttonVariants({ variant: "outline" }))}
        >
          Xuất Phụ đề (.srt)
        </a>
      </div>
    </div>
  );
}
