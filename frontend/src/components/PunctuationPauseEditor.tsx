"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Plus, Trash2 } from "lucide-react";

const MAX_MS = 1000;

interface Props {
  value: Record<string, number>;
  onChange: (next: Record<string, number>) => void;
}

export default function PunctuationPauseEditor({ value, onChange }: Props) {
  const [newKey, setNewKey] = useState("");
  const [newMs, setNewMs] = useState("200");

  const keys = Object.keys(value);

  function setMs(key: string, ms: number) {
    onChange({ ...value, [key]: Math.max(0, Math.round(ms)) });
  }

  function removeKey(key: string) {
    const next = { ...value };
    delete next[key];
    onChange(next);
  }

  function addKey() {
    const key = newKey.trim();
    if (!key || key in value) return;
    const ms = Number(newMs);
    onChange({ ...value, [key]: Number.isFinite(ms) ? Math.max(0, Math.round(ms)) : 0 });
    setNewKey("");
    setNewMs("200");
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Dấu câu (hoặc token đặc biệt) → độ dài khoảng lặng (ms). Dùng cho ngắt nghỉ ngắn bên trong
        1 đoạn. Có hiệu lực ngay khi lưu, không cần khởi động lại backend.
      </p>

      {keys.length === 0 && (
        <p className="text-xs italic text-muted-foreground">Chưa có mục nào.</p>
      )}

      <div className="space-y-2">
        {keys.map((key) => (
          <div key={key} className="flex items-center gap-2 rounded-lg border p-2">
            <span className="w-28 shrink-0 truncate rounded bg-muted px-1.5 py-0.5 text-center font-mono text-xs">
              {key}
            </span>
            <Slider
              min={0}
              max={MAX_MS}
              step={10}
              value={[value[key] ?? 0]}
              onValueChange={(v) => setMs(key, Array.isArray(v) ? v[0] : v)}
              className="flex-1"
            />
            <Input
              type="number"
              min={0}
              value={value[key] ?? 0}
              onChange={(e) => setMs(key, Number(e.target.value) || 0)}
              className="h-7 w-16 shrink-0 text-xs"
            />
            <span className="w-6 shrink-0 text-xs text-muted-foreground">ms</span>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => removeKey(key)}
              aria-label={`Xoá mục ${key}`}
              className="shrink-0"
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-1.5 border-t pt-2">
        <Input
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          placeholder="Dấu câu / token mới (vd: ~)"
          className="h-7 text-xs"
        />
        <Input
          type="number"
          min={0}
          value={newMs}
          onChange={(e) => setNewMs(e.target.value)}
          className="h-7 w-20 shrink-0 text-xs"
        />
        <span className="shrink-0 text-xs text-muted-foreground">ms</span>
        <Button size="sm" variant="outline" onClick={addKey} className="shrink-0">
          <Plus /> Thêm
        </Button>
      </div>
    </div>
  );
}
