"use client";

import { useState } from "react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "cn";
import type { ChapterDiff } from "@/lib/types";

interface Props {
  diffs: ChapterDiff[];
}

// Phase 3 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md, muc 12 - "diff
// view": corrected_text cua Beta duoc TINH tu truoc nhung chua bao gio den
// duoc frontend (cung mau hinh "agent tinh, san pham vut bo" nhu Phase 0).
// Minh bach thuan tuy, khong doi model - chi hien thi lai chinh xac Beta da
// sua/chen gi so voi van ban goc cua Alpha.
function DiffChapter({ diff }: { diff: ChapterDiff }) {
  const [open, setOpen] = useState(false);
  const hasChanges = diff.diff_ops.some((op) => op.op !== "equal");
  if (!hasChanges) return null;

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-lg border">
      <CollapsibleTrigger
        className={cn(
          buttonVariants({ variant: "ghost" }),
          "w-full justify-between px-4 py-3 h-auto"
        )}
      >
        <span className="text-sm font-medium">Xem thay đổi của Beta (Chương {diff.chapter})</span>
        <span className="text-xs text-muted-foreground">{open ? "Thu gọn" : "Mở rộng"}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="px-4 pb-4">
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {diff.diff_ops.map((op, i) => {
            if (op.op === "delete") {
              return (
                <span key={i} className="line-through text-destructive/70">
                  {op.text}{" "}
                </span>
              );
            }
            if (op.op === "insert") {
              return (
                <span key={i} className="bg-jade/15 text-jade">
                  {op.text}{" "}
                </span>
              );
            }
            return <span key={i}>{op.text} </span>;
          })}
        </p>
      </CollapsibleContent>
    </Collapsible>
  );
}

export default function DiffView({ diffs }: Props) {
  const chaptersWithChanges = diffs.filter((d) => d.diff_ops.some((op) => op.op !== "equal"));
  if (chaptersWithChanges.length === 0) return null;

  return (
    <div className="space-y-2">
      {diffs.map((diff) => (
        <DiffChapter key={diff.chapter} diff={diff} />
      ))}
    </div>
  );
}
