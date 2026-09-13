"use client";

import { Badge } from "@/components/ui/badge";
import type { SubmitResponse } from "@/lib/types";

interface Props {
  result: SubmitResponse;
}

// Phase 2 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Richer genre
// signal") - nhan hien thi tieng Viet cho 3 truong tone/pacing/target_audience
// (gia tri tho la Literal khong dau trong voxdirector/agents/alpha_ingestion.py,
// dung de cham diem giong o backend - map rieng sang nhan hien thi o day,
// khong doi gia tri tho vi backend/eval harness dua vao dung chuoi do).
const TONE_LABELS: Record<string, string> = { u_toi: "u ám", tuoi_sang: "tươi sáng" };
const PACING_LABELS: Record<string, string> = { nhanh: "nhanh", cham: "chậm" };
const AUDIENCE_LABELS: Record<string, string> = {
  thieu_nhi: "thiếu nhi",
  thanh_thieu_nien: "thanh thiếu niên",
  nguoi_lon: "người lớn",
};

// Chi con hien thi the loai phat hien duoc (2026-09-12) - viec chon giong da
// gop chung vao VoicePicker o LeftColumn.tsx (luon hien, khong con rieng 1
// dropdown o day nua) de tranh 2 noi dieu khien cung 1 gia tri.
export default function GenreVoiceSuggestion({ result }: Props) {
  if (!result.detected_genre) return null;

  const tagLine = [
    result.tone && TONE_LABELS[result.tone],
    result.pacing && PACING_LABELS[result.pacing],
    result.target_audience && AUDIENCE_LABELS[result.target_audience],
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="rounded-lg border bg-muted/30 p-4 space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Thể loại phát hiện</span>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{result.detected_genre}</Badge>
          <span className="text-xs text-muted-foreground font-mono">
            {Math.round(result.genre_confidence_score * 100)}% tin cậy
          </span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{result.chapters} chương phát hiện được.</p>
      {tagLine && <p className="text-xs text-muted-foreground">Giọng điệu: {tagLine}.</p>}
      {result.chapters_needing_review > 0 && (
        <p className="text-xs text-amber-600 dark:text-amber-500">
          ⚠ {result.chapters_needing_review} chương cần xem lại ranh giới tách chương.
        </p>
      )}
    </div>
  );
}
