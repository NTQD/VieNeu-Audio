"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2 } from "lucide-react";
import {
  deleteLiveGlossaryEntry,
  fetchLiveGlossaryEntries,
  suggestGlossaryLabel,
  upsertLiveGlossaryEntry,
} from "@/lib/api";
import type { GlossaryEntry } from "@/lib/types";

const ENTITY_TYPES: { value: GlossaryEntry["entity_type"]; label: string }[] = [
  { value: "character", label: "Nhân vật" },
  { value: "place", label: "Địa danh" },
  { value: "term", label: "Thuật ngữ" },
];

function blankEntry(): GlossaryEntry {
  return {
    original_term: "",
    entity_type: "character",
    canonical_form: "",
    pronunciation_note: null,
    first_seen_chapter: null,
  };
}

// 2026-09-14 - "Glossary dang dung": doc/ghi TRUC TIEP tren ChromaDB qua
// GET/POST/DELETE /api/glossary - KHAC voi "Glossary khoi tao" o tren
// (GlossaryEditor.tsx, sua file JSON tinh data/glossary_seed.json). Sinh ra
// de fix bao cao "duyệt xong nhưng dữ liệu không được lưu": approve_new_entries()
// (goi tu NewTermConfirmationPanel) van LUON ghi dung vao ChromaDB - chi la
// truoc day KHONG CO CHO NAO tren UI hien lai duoc dung du lieu do, nguoi
// dung tuong nham dang xem "glossary that" khi mo Glossary khoi tao (thuc ra
// la file seed tinh, khong lien quan). Moi entry o day duoc luu/xoa NGAY LAP
// TUC (khong co nut "Luu" chung cho ca danh sach) vi ChromaDB la 1 tap hop
// document doc lap, khac voi 3 file JSON kia (ghi de nguyen file 1 lan).
export default function LiveGlossaryManager() {
  const [entries, setEntries] = useState<GlossaryEntry[] | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [rowState, setRowState] = useState<Record<string, "idle" | "saving" | "deleting" | "error">>({});
  const [rowError, setRowError] = useState<Record<string, string>>({});
  const [newEntry, setNewEntry] = useState<GlossaryEntry>(blankEntry());
  const [addStatus, setAddStatus] = useState<"idle" | "saving" | "error">("idle");
  const [addError, setAddError] = useState<string | null>(null);
  // Ref (khong phai state) - chi doc trong callback debounce, khong can
  // trigger re-render khi doi; danh dau nguoi dung DA tu chon loai thu cong
  // cho lan go term nay, de goi y tu dong (bat dong bo, den SAU) khong ghi
  // de lua chon do.
  const labelManuallySet = useRef(false);
  const suggestDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const data = await fetchLiveGlossaryEntries();
      setEntries(data);
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tải thất bại");
      setStatus("error");
    }
  }

  function updateEntry(term: string, patch: Partial<GlossaryEntry>) {
    setEntries((prev) =>
      prev ? prev.map((e) => (e.original_term === term ? { ...e, ...patch } : e)) : prev
    );
  }

  async function saveEntry(entry: GlossaryEntry) {
    setRowState((s) => ({ ...s, [entry.original_term]: "saving" }));
    setRowError((s) => ({ ...s, [entry.original_term]: "" }));
    try {
      await upsertLiveGlossaryEntry(entry);
      setRowState((s) => ({ ...s, [entry.original_term]: "idle" }));
    } catch (err) {
      setRowState((s) => ({ ...s, [entry.original_term]: "error" }));
      setRowError((s) => ({
        ...s,
        [entry.original_term]: err instanceof Error ? err.message : "Lưu thất bại",
      }));
    }
  }

  async function removeEntry(term: string) {
    setRowState((s) => ({ ...s, [term]: "deleting" }));
    try {
      await deleteLiveGlossaryEntry(term);
      setEntries((prev) => (prev ? prev.filter((e) => e.original_term !== term) : prev));
    } catch (err) {
      setRowState((s) => ({ ...s, [term]: "error" }));
      setRowError((s) => ({
        ...s,
        [term]: err instanceof Error ? err.message : "Xoá thất bại",
      }));
    }
  }

  // Goi y nhan (entity_type) theo tu khoa khi nguoi dung go term moi - go
  // term MOI (khac voi truoc) coi nhu 1 candidate moi, xoa co "da tu chon
  // thu cong" cua candidate cu. Neu nguoi dung tu chon loai (Select's
  // onValueChange) TRUOC KHI goi y bat dong bo nay tra ve, labelManuallySet
  // se la true va goi y bi bo qua - tranh ghi de lua chon thu cong.
  function handleNewTermChange(term: string) {
    setNewEntry((e) => ({ ...e, original_term: term }));
    labelManuallySet.current = false;
    if (suggestDebounce.current) clearTimeout(suggestDebounce.current);
    if (!term.trim()) return;
    suggestDebounce.current = setTimeout(async () => {
      try {
        const suggested = await suggestGlossaryLabel(term);
        if (labelManuallySet.current) return;
        setNewEntry((e) => (e.original_term === term ? { ...e, entity_type: suggested } : e));
      } catch {
        // Goi y chi la tien ich phu - loi o day khong can bao, nguoi dung
        // van tu chon loai duoc binh thuong qua dropdown.
      }
    }, 400);
  }

  async function addEntry() {
    if (!newEntry.original_term.trim() || !newEntry.canonical_form.trim()) {
      setAddError("Cần điền Tên gốc và Tên chuẩn hoá.");
      setAddStatus("error");
      return;
    }
    setAddStatus("saving");
    setAddError(null);
    try {
      await upsertLiveGlossaryEntry(newEntry);
      setEntries((prev) => [...(prev ?? []), newEntry]);
      setNewEntry(blankEntry());
      labelManuallySet.current = false;
      setAddStatus("idle");
    } catch (err) {
      setAddStatus("error");
      setAddError(err instanceof Error ? err.message : "Thêm thất bại");
    }
  }

  useEffect(() => {
    return () => {
      if (suggestDebounce.current) clearTimeout(suggestDebounce.current);
    };
  }, []);

  return (
    <div className="space-y-2 border-t pt-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Glossary đang dùng (thời gian thực)</p>
          <p className="text-xs text-muted-foreground">
            Đọc/ghi trực tiếp trên ChromaDB — nơi các thuật ngữ đã &ldquo;Duyệt&rdquo; thực sự được
            lưu (khác với &ldquo;Glossary khởi tạo&rdquo; ở trên, chỉ là file seed tĩnh).
          </p>
        </div>
        {entries === null && (
          <Button size="sm" variant="outline" onClick={load} disabled={status === "loading"}>
            {status === "loading" ? "Đang tải..." : "Tải để xem"}
          </Button>
        )}
      </div>

      {status === "error" && <p className="text-xs text-destructive">{error}</p>}

      {entries !== null && (
        <div className="space-y-3">
          {entries.length === 0 && (
            <p className="text-xs italic text-muted-foreground">
              Glossary đang dùng chưa có entry nào (chưa có thuật ngữ nào được duyệt).
            </p>
          )}

          <div className="space-y-2">
            {entries.map((entry) => {
              const state = rowState[entry.original_term] ?? "idle";
              const missingRequired =
                !entry.original_term.trim() || !entry.canonical_form.trim();
              return (
                <Card key={entry.original_term} size="sm">
                  <CardContent className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="grid flex-1 grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <Label className="text-xs text-muted-foreground">Tên gốc</Label>
                          <Input value={entry.original_term} disabled className="h-7 text-xs" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs text-muted-foreground">Tên chuẩn hoá</Label>
                          <Input
                            value={entry.canonical_form}
                            onChange={(e) =>
                              updateEntry(entry.original_term, { canonical_form: e.target.value })
                            }
                            className="h-7 text-xs"
                          />
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => removeEntry(entry.original_term)}
                        disabled={state === "deleting"}
                        aria-label={`Xoá entry ${entry.original_term}`}
                        className="mt-4.5 shrink-0"
                      >
                        <Trash2 />
                      </Button>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">Loại</Label>
                        <Select
                          value={entry.entity_type}
                          onValueChange={(v) =>
                            updateEntry(entry.original_term, {
                              entity_type: v as GlossaryEntry["entity_type"],
                            })
                          }
                        >
                          <SelectTrigger size="sm" className="h-7 w-full text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {ENTITY_TYPES.map((t) => (
                              <SelectItem key={t.value} value={t.value}>
                                {t.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">Xuất hiện từ chương</Label>
                        <Input
                          type="number"
                          min={1}
                          value={entry.first_seen_chapter ?? ""}
                          onChange={(e) =>
                            updateEntry(entry.original_term, {
                              first_seen_chapter:
                                e.target.value === "" ? null : Number(e.target.value),
                            })
                          }
                          placeholder="(tuỳ chọn)"
                          className="h-7 text-xs"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => saveEntry(entry)}
                        disabled={state === "saving" || missingRequired}
                      >
                        {state === "saving" ? "Đang lưu..." : "Lưu"}
                      </Button>
                      {state === "error" && (
                        <p className="text-[0.7rem] text-destructive">
                          {rowError[entry.original_term]}
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <Card size="sm" className="border-dashed">
            <CardContent className="space-y-2">
              <p className="text-xs font-medium">Thêm thuật ngữ mới</p>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Tên gốc</Label>
                  <Input
                    value={newEntry.original_term}
                    onChange={(e) => handleNewTermChange(e.target.value)}
                    placeholder="vd: Huyết Nguyệt Tông"
                    className="h-7 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Tên chuẩn hoá</Label>
                  <Input
                    value={newEntry.canonical_form}
                    onChange={(e) => setNewEntry((v) => ({ ...v, canonical_form: e.target.value }))}
                    placeholder="vd: Huyết Nguyệt Tông"
                    className="h-7 text-xs"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">
                  Loại (tự động gợi ý theo tên gốc, có thể sửa)
                </Label>
                <Select
                  value={newEntry.entity_type}
                  onValueChange={(v) => {
                    labelManuallySet.current = true;
                    setNewEntry((e) => ({ ...e, entity_type: v as GlossaryEntry["entity_type"] }));
                  }}
                >
                  <SelectTrigger size="sm" className="h-7 w-full text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ENTITY_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {addStatus === "error" && addError && (
                <p className="text-[0.7rem] text-destructive">{addError}</p>
              )}
              <Button size="sm" variant="outline" onClick={addEntry} disabled={addStatus === "saving"} className="w-full">
                <Plus /> {addStatus === "saving" ? "Đang thêm..." : "Thêm entry"}
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
