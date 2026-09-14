"use client";

import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { fetchSettingsFile, uploadSettingsFile } from "@/lib/api";

export type SettingsKey = "emotion-lexicon" | "glossary-seed" | "punctuation-pauses";

// Ca 3 file du lieu deu mang theo metadata "_placeholder"/"_note" (xem
// data/*.json) - khong hien thi cho nguoi dung sua nhung PHAI giu nguyen khi
// luu lai, khong thi mat ghi chu goc cua team.
export function isMetaKey(key: string) {
  return key.startsWith("_");
}

export function metaOf(raw: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(raw).filter(([k]) => isMetaKey(k)));
}

// Chrome chung (tai/luu/dong/trang thai loi) cho cac khoi cai dat dang
// "1 file JSON, thay-the-toan-bo-luc-luu" - moi khoi chi khac nhau o kieu du
// lieu T va giao dien sua T (children render-prop), thay vi lap lai textarea
// + JSON.parse/stringify nhu truoc (khong than thien nguoi dung khong ranh
// JSON). Tach rieng khoi SettingsPanel.tsx (2026-09-14) de GlossaryManagerDialog.tsx
// cung dung lai duoc cho tab "Khởi tạo", khong phai dinh nghia lai.
export function SettingsSectionShell<T>({
  label,
  hint,
  settingsKey,
  toContent,
  toRaw,
  validate,
  children,
}: {
  label: string;
  hint: string;
  settingsKey: SettingsKey;
  toContent: (raw: Record<string, unknown>) => T;
  toRaw: (content: T, raw: Record<string, unknown>) => Record<string, unknown>;
  validate?: (content: T) => string | null;
  children: (content: T, setContent: (next: T) => void) => ReactNode;
}) {
  const [raw, setRaw] = useState<Record<string, unknown> | null>(null);
  const [content, setContent] = useState<T | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "saving" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const data = await fetchSettingsFile(settingsKey);
      setRaw(data);
      setContent(toContent(data));
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tải thất bại");
      setStatus("error");
    }
  }

  async function save() {
    if (content === null) return;
    const validationError = validate?.(content) ?? null;
    if (validationError) {
      setError(validationError);
      setStatus("error");
      return;
    }
    setStatus("saving");
    setError(null);
    try {
      await uploadSettingsFile(settingsKey, toRaw(content, raw ?? {}));
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại");
      setStatus("error");
    }
  }

  function close() {
    setRaw(null);
    setContent(null);
    setStatus("idle");
    setError(null);
  }

  return (
    <div className="space-y-2 border-t pt-4 first:border-t-0 first:pt-0">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        {content === null && (
          <Button size="sm" variant="outline" onClick={load} disabled={status === "loading"}>
            {status === "loading" ? "Đang tải..." : "Tải để sửa"}
          </Button>
        )}
      </div>
      {content !== null && (
        <div className="space-y-3">
          {children(content, setContent)}
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={save} disabled={status === "saving"}>
              {status === "saving" ? "Đang lưu..." : "Lưu"}
            </Button>
            <Button size="sm" variant="ghost" onClick={close}>
              Đóng
            </Button>
          </div>
        </div>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
