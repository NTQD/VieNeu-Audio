"use client";

import type { ExpressionReportItem, PauseReportItem } from "@/lib/types";

interface Props {
  expressionReport: ExpressionReportItem[];
  pauseReport: PauseReportItem[];
}

// Section 5b cua PHASE0_HANDOFF.md - truoc ban sua nay, expression_report/
// pause_report cua Beta duoc tinh xong roi bi orchestrator.py vut bo, chua
// bao gio den frontend. Panel nho, tach rieng thay vi gan vao tung dong cua
// SegmentList - 2 report nay danh so theo doan Alpha gan co (khong phai theo
// chunk TTS) va KHONG kem vi tri/quoted_text rieng, nen khong the anh xa 1-1
// vao 1 dong segment cu the (xem docstring ExpressionReportItem/PauseReportItem
// trong voxdirector/agents/beta_consistency.py).
export default function BetaActivityPanel({ expressionReport, pauseReport }: Props) {
  if (expressionReport.length === 0 && pauseReport.length === 0) return null;

  return (
    <div className="rounded-lg border p-3 space-y-1.5">
      <span className="text-sm font-medium">Beta hoạt động</span>
      <ul className="space-y-1 text-xs text-muted-foreground font-mono">
        {expressionReport.map((item, i) => (
          <li key={`expr-${i}`}>
            {item.matched
              ? `chèn biểu cảm [${item.emotion_label}]: "${item.inserted_word}"`
              : `bỏ qua biểu cảm [${item.emotion_label}]: ${item.skipped_reason ?? "không rõ lý do"}`}
          </li>
        ))}
        {pauseReport.map((item, i) => (
          <li key={`pause-${i}`}>
            {item.matched
              ? "chèn ngắt nghỉ dài"
              : `bỏ qua ngắt nghỉ dài: ${item.skipped_reason ?? "không rõ lý do"}`}
          </li>
        ))}
      </ul>
    </div>
  );
}
