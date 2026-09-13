"use client";

import { Sparkles, ScanText, ShieldCheck } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { cn } from "cn";
import type { AdvancedOptionsState } from "@/lib/types";

interface Props {
  value: AdvancedOptionsState;
  onChange: (next: AdvancedOptionsState) => void;
}

const AGENTS = [
  {
    key: "alphaEnabled" as const,
    name: "Alpha",
    icon: ScanText,
    role: "Phân tích chương & thể loại",
    offNote: "Tắt: tách chương bằng quy tắc đơn giản, không nhận diện thể loại/cảm xúc.",
  },
  {
    key: "betaEnabled" as const,
    name: "Beta",
    icon: Sparkles,
    role: "Nhất quán thuật ngữ & biểu cảm",
    offNote: "Tắt: đọc nguyên văn bản gốc, không chèn từ biểu cảm/khoảng ngắt dài.",
  },
  {
    key: "qaEnabled" as const,
    name: "Gamma",
    icon: ShieldCheck,
    role: "Kiểm tra chất lượng bằng ASR",
    offNote: null,
  },
];

// "Ban dieu khien Agent" - 2026-09-12, thay the cho viec chon giau 3 cong tac
// Agent trong "Tuy chon nang cao": vi day gio la 3 khoi dieu khien co lieu
// AI that su cua san pham (khong phai tuy chon phu), can hien thi ngang hang
// voi giong doc/van ban, KHONG bi thu gon mac dinh.
export default function AgentRail({ value, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
      {AGENTS.map(({ key, name, icon: Icon, role, offNote }) => {
        const enabled = value[key];
        return (
          <div
            key={key}
            className={cn(
              "rounded-lg border p-3 space-y-1.5 transition-colors",
              enabled ? "bg-card border-border" : "bg-muted/40 border-transparent"
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Icon className={cn("size-4", enabled ? "text-lacquer" : "text-muted-foreground")} />
                <span className="font-display text-sm font-semibold">{name}</span>
              </div>
              <Switch
                checked={enabled}
                onCheckedChange={(checked) => onChange({ ...value, [key]: checked })}
                aria-label={`Bật/tắt Agent ${name}`}
              />
            </div>
            <p className="text-xs text-muted-foreground leading-snug">{role}</p>
            {!enabled && offNote && (
              <p className="text-xs text-muted-foreground/80 leading-snug italic">{offNote}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
