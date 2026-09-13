"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { SegmentInfo } from "@/lib/types";

interface Props {
  segments: SegmentInfo[];
  onRerender: (segmentId: number) => void;
  rerenderingId?: number | null;
}

export default function SegmentList({ segments, onRerender, rerenderingId = null }: Props) {
  return (
    <div className="space-y-2">
      <p className="font-display text-sm font-medium">Bản chép lời (transcript)</p>
      <ul className="space-y-1.5">
        {segments.map((seg) => (
          <li
            key={seg.id}
            className={`flex items-center justify-between gap-3 rounded-lg border p-3 text-sm transition-colors ${
              seg.flagged ? "border-destructive/40 bg-destructive/5" : "bg-card"
            }`}
          >
            <div className="flex items-center gap-2 min-w-0">
              {seg.flagged && (
                <Badge variant="destructive" className="shrink-0">
                  Nghi ngờ lỗi
                </Badge>
              )}
              <span className="truncate">{seg.text}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {seg.duration_s !== null && (
                <span className="text-xs text-muted-foreground font-mono">{seg.duration_s.toFixed(1)}s</span>
              )}
              <Button
                size="sm"
                variant="outline"
                disabled={rerenderingId === seg.id}
                onClick={() => onRerender(seg.id)}
              >
                {rerenderingId === seg.id ? "Đang render..." : "Render lại"}
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
