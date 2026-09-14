"use client";

import { useEffect, useState, type ReactNode } from "react";
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

// Load/luu 1 file settings dang "thay-the-toan-bo-luc-luu" - moi khoi chi
// khac nhau o kieu du lieu T va giao dien sua T (children render-prop).
//
// 2026-09-14 - TU DONG TAI ngay luc mount (truoc day can bam "Tai de sua"
// rieng) - kể từ khi mỗi khối này chuyển vào hẳn 1 DataViewerDialog riêng
// (xem SettingsPanel.tsx/GlossaryManagerDialog.tsx), MỞ dialog đã LÀ hành
// động "tôi muốn xem/sửa cái này" rồi, thêm 1 nút xác nhận nữa là thừa. Bỏ
// luôn tiêu đề/mô tả/nút "Đóng" riêng của khối này (DialogTitle + đóng dialog
// của DataViewerDialog đã lo phần đó) - component này giờ CHỈ còn là vùng
// nội dung.
//
// 2026-09-15 - nut Luu KHONG con tu render o day nua (truoc day la 1 thanh
// sticky-bottom rieng cua shell nay). Yeu cau nguoi dung: Them/Xoa/Luu phai
// la TAI NGUYEN DUNG CHUNG cua ca bang, khong phai rieng le - moi editor con
// (Emotion/Glossary/Punctuation) gio tu render 1 TableToolbar DUY NHAT gom
// ca 3 nut, dat canh checkbox "chon tat ca"/nut Xoa da chon. Shell nay chi
// con lo phan tai du lieu + co che luu, expose ra ngoai qua tham so thu 3
// cua children thay vi tu ve UI.
export type SaveController = {
  save: () => void;
  status: "idle" | "loading" | "saving" | "error";
  error: string | null;
};

export function SettingsSectionShell<T>({
  settingsKey,
  toContent,
  toRaw,
  validate,
  children,
}: {
  settingsKey: SettingsKey;
  toContent: (raw: Record<string, unknown>) => T;
  toRaw: (content: T, raw: Record<string, unknown>) => Record<string, unknown>;
  validate?: (content: T) => string | null;
  children: (content: T, setContent: (next: T) => void, table: SaveController) => ReactNode;
}) {
  const [raw, setRaw] = useState<Record<string, unknown> | null>(null);
  const [content, setContent] = useState<T | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "saving" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setError(null);
    fetchSettingsFile(settingsKey)
      .then((data) => {
        if (cancelled) return;
        setRaw(data);
        setContent(toContent(data));
        setStatus("idle");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Tải thất bại");
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- settingsKey la hang so tinh cho 1 instance, toContent doi moi lan render nen KHONG dua vao deps (se lap lai fetch vo han).
  }, [settingsKey]);

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

  if (content === null) {
    return (
      <p className="text-sm text-muted-foreground">
        {status === "error" ? (error ?? "Tải thất bại") : "Đang tải..."}
      </p>
    );
  }

  return <>{children(content, setContent, { save, status, error: status === "error" ? error : null })}</>;
}
