"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { NewTermCandidate } from "@/lib/types";

interface Props {
  candidates: NewTermCandidate[];
  onDismiss: () => void;
  onApprove: (term: string) => void;
}

// Overlay/panel nho, khong chan (non-blocking), hien tren CA HAI trang thai
// layout (desktop 2-cot / mobile stacked) - Section 8.1.1 cua spec. Xuat
// hien khi Beta co new_entry_candidates can nguoi dung duyet.
export default function NewTermConfirmationPanel({ candidates, onDismiss, onApprove }: Props) {
  if (candidates.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 w-[340px] rounded-lg border bg-background p-4 shadow-lg">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium">Thuật ngữ mới phát hiện</p>
        <Button variant="ghost" size="sm" onClick={onDismiss}>
          ✕
        </Button>
      </div>
      <ul className="space-y-2">
        {candidates.map((c) => (
          <li key={c.term} className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm truncate">{c.term}</span>
              <Badge variant="secondary" className="shrink-0">
                {c.entity_type}
              </Badge>
            </div>
            <Button size="sm" onClick={() => onApprove(c.term)}>
              Duyệt
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
