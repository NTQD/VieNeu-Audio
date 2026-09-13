"use client";

import { ScanText, Sparkles, AudioLines, Layers, ShieldCheck, Check } from "lucide-react";
import { cn } from "cn";
import type { ProgressMessage } from "@/lib/types";

interface Props {
  latest: ProgressMessage | null;
}

const NODES = [
  { key: "alpha", label: "Alpha", icon: ScanText },
  { key: "beta", label: "Beta", icon: Sparkles },
  { key: "tts", label: "Giọng đọc", icon: AudioLines },
  { key: "assemble", label: "Ghép", icon: Layers },
  { key: "qa", label: "Gamma", icon: ShieldCheck },
] as const;

// "Duong ong AI" - 2026-09-12: thay progress-bar phang bang 1 chuoi node
// sang/mo dan theo dung cau truc that cua san pham (Alpha -> Beta -> TTS ->
// Ghep -> Gamma) - day la CAU CHUYEN that cua VoxDirector (nhieu Agent phoi
// hop), khong phai 1 thanh tai % chung chung.
export default function ProgressStages({ latest }: Props) {
  const stageIndex = latest?.stage_index ?? 0;

  return (
    <div className="space-y-6 w-full">
      <div className="flex items-center justify-between">
        {NODES.map((node, i) => {
          const isDone = i < stageIndex;
          const isCurrent = i === stageIndex;
          const Icon = node.icon;
          return (
            <div key={node.key} className="flex flex-1 items-center last:flex-none">
              <div className="flex flex-col items-center gap-1.5">
                <div className="relative flex size-10 items-center justify-center">
                  {/* Vong tron xoay quanh icon dang chay - yeu cau nguoi dung
                      (2026-09-13): "loading effect... green circle rotating
                      around the circular icon". Vien voi 1 canh trong suot
                      (border-t-transparent) + animate-spin cua Tailwind tao
                      hieu ung spinner chuan, mau jade (xanh la) theo dung yeu
                      cau - tach rieng khoi vien mau cua chinh icon (lacquer/
                      do) o duoi, khong doi mau nen "dang chay" hien co. */}
                  {isCurrent && (
                    <div className="absolute -inset-1 rounded-full border-2 border-jade border-t-transparent animate-spin" />
                  )}
                  <div
                    className={cn(
                      "flex size-10 items-center justify-center rounded-full border-2 transition-colors",
                      isDone && "border-jade bg-jade/15 text-jade",
                      isCurrent && "border-lacquer bg-lacquer/15 text-lacquer",
                      !isDone && !isCurrent && "border-border text-muted-foreground"
                    )}
                  >
                    {isDone ? <Check className="size-4" /> : <Icon className="size-4" />}
                  </div>
                </div>
                <span
                  className={cn(
                    "text-xs font-medium",
                    isCurrent ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {node.label}
                </span>
              </div>
              {i < NODES.length - 1 && (
                <div className={cn("mx-1 h-0.5 flex-1 rounded-full", isDone ? "bg-jade" : "bg-border")} />
              )}
            </div>
          );
        })}
      </div>
      <p className="text-center text-sm text-muted-foreground">
        {latest?.label ?? "Đang khởi động..."}
      </p>
    </div>
  );
}
