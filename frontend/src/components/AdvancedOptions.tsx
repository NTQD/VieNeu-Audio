"use client";

import { useState } from "react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "cn";
import type { AdvancedOptionsState } from "@/lib/types";

interface Props {
  value: AdvancedOptionsState;
  onChange: (next: AdvancedOptionsState) => void;
}

// "Cai dat san xuat" (doi ten tu "Tuy chon nang cao", 2026-09-12) - CHI con
// cac muc THUC SU phu/it dung (anh nen/nhac nen/khoang lang/phu de). Giong
// doc va Agent (Alpha/Beta/Gamma) da chuyen thanh dieu khien hang dau, luon
// hien (xem VoicePicker + AgentRail trong LeftColumn.tsx) - khong con hop ly
// khi giau chung trong 1 accordion dong mac dinh nhu truoc.
export default function AdvancedOptions({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-lg border">
      <CollapsibleTrigger
        className={cn(
          buttonVariants({ variant: "ghost" }),
          "w-full justify-between px-4 py-3 h-auto"
        )}
      >
        <span className="text-sm font-medium">Cài đặt sản xuất</span>
        <span className="text-xs text-muted-foreground">{open ? "Thu gọn" : "Mở rộng"}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="px-4 pb-4 space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="bg-image">Ảnh nền (tuỳ chọn — cần để xuất video)</Label>
          <input
            id="bg-image"
            type="file"
            accept="image/*"
            className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-sm"
            onChange={(e) =>
              onChange({ ...value, backgroundImage: e.target.files?.[0] ?? null })
            }
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="bg-music">Nhạc nền (tuỳ chọn)</Label>
          <input
            id="bg-music"
            type="file"
            accept="audio/*"
            className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-sm"
            onChange={(e) =>
              onChange({ ...value, backgroundMusic: e.target.files?.[0] ?? null })
            }
          />
          {value.backgroundMusic && (
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center justify-between">
                <Label>Âm lượng nhạc nền</Label>
                <span className="text-xs text-muted-foreground font-mono">
                  {Math.round(value.bgmVolume * 100)}%
                </span>
              </div>
              <Slider
                min={0}
                max={0.5}
                step={0.01}
                value={[value.bgmVolume]}
                onValueChange={(v) =>
                  onChange({ ...value, bgmVolume: Array.isArray(v) ? v[0] : v })
                }
              />
              <p className="text-xs text-muted-foreground">
                Nhạc nền sẽ tự động lặp lại nếu ngắn hơn, hoặc bị cắt bớt nếu dài hơn giọng đọc.
              </p>
            </div>
          )}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label>Khoảng lặng mặc định giữa các phần</Label>
            <span className="text-xs text-muted-foreground font-mono">{value.pauseDurationMs}ms</span>
          </div>
          <Slider
            min={200}
            max={800}
            step={50}
            value={[value.pauseDurationMs]}
            onValueChange={(v) =>
              onChange({ ...value, pauseDurationMs: Array.isArray(v) ? v[0] : v })
            }
          />
        </div>

        <div className="flex items-center justify-between">
          <Label htmlFor="burn-subs">Ghi cứng phụ đề vào video</Label>
          <Switch
            id="burn-subs"
            checked={value.burnSubtitles}
            onCheckedChange={(checked) => onChange({ ...value, burnSubtitles: checked })}
          />
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
