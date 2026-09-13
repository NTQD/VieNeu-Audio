"use client";

import { Badge } from "@/components/ui/badge";
import type { SubmitResponse } from "@/lib/types";

interface Props {
  result: SubmitResponse;
}

// Chi con hien thi the loai phat hien duoc (2026-09-12) - viec chon giong da
// gop chung vao VoicePicker o LeftColumn.tsx (luon hien, khong con rieng 1
// dropdown o day nua) de tranh 2 noi dieu khien cung 1 gia tri.
export default function GenreVoiceSuggestion({ result }: Props) {
  if (!result.detected_genre) return null;

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
      {result.chapters_needing_review > 0 && (
        <p className="text-xs text-amber-600 dark:text-amber-500">
          ⚠ {result.chapters_needing_review} chương cần xem lại ranh giới tách chương.
        </p>
      )}
    </div>
  );
}
