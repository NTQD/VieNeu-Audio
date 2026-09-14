"use client";

import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
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
import TableToolbar from "@/components/TableToolbar";
import type { SaveController } from "@/components/SettingsSectionShell";
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

interface Props {
  value: GlossaryEntry[];
  onChange: (next: GlossaryEntry[]) => void;
  table: SaveController;
}

// 2026-09-15 - nut Xoa RIENG tren tung the (Card) va nut Them duoi bang gio
// gop chung vao 1 TableToolbar DUY NHAT o dau (xem TableToolbar.tsx) - checkbox
// chon dong (chi so mang lam id, mang nay von da la array nen khong co van de
// doi-ten-key nhu Emotion/Punctuation) + "Xoa da chon" xoa nhieu entry 1 luc
// thay vi bam tung nut Xoa rieng cho tung entry.
export default function GlossaryEditor({ value, onChange, table }: Props) {
  const [selected, setSelected] = useState<Set<number>>(new Set());

  function updateEntry(index: number, patch: Partial<GlossaryEntry>) {
    onChange(value.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)));
  }

  function addEntry() {
    onChange([...value, blankEntry()]);
  }

  function deleteSelected() {
    onChange(value.filter((_, i) => !selected.has(i)));
    setSelected(new Set());
  }

  function toggleAll(checked: boolean) {
    setSelected(checked ? new Set(value.map((_, i) => i)) : new Set());
  }

  function toggleRow(index: number, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(index);
      else next.delete(index);
      return next;
    });
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Danh sách entry ban đầu cho Character/Terminology Glossary (nạp vào ChromaDB khi pipeline
        khởi động). <span className="font-medium">Tên gốc</span> và{" "}
        <span className="font-medium">Tên chuẩn hoá</span> là bắt buộc.
      </p>

      <TableToolbar
        totalCount={value.length}
        selectedCount={selected.size}
        onToggleAll={toggleAll}
        onAdd={addEntry}
        addLabel="Thêm entry"
        onDeleteSelected={deleteSelected}
        onSave={table.save}
        saving={table.status === "saving"}
        error={table.error}
      />

      {value.length === 0 && (
        <p className="text-xs italic text-muted-foreground">Chưa có entry nào.</p>
      )}

      <div className="space-y-2">
        {value.map((entry, index) => {
          const missingRequired = !entry.original_term.trim() || !entry.canonical_form.trim();
          return (
            <Card key={index} size="sm">
              <CardContent className="space-y-2">
                <div className="flex items-start gap-2">
                  <Checkbox
                    checked={selected.has(index)}
                    onCheckedChange={(checked) => toggleRow(index, checked === true)}
                    aria-label={`Chọn entry ${entry.original_term || index + 1}`}
                    className="mt-1.5 shrink-0"
                  />
                  <div className="grid flex-1 grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Tên gốc</Label>
                      <Input
                        value={entry.original_term}
                        onChange={(e) => updateEntry(index, { original_term: e.target.value })}
                        placeholder="vd: Lý Phong"
                        className="h-7 text-xs"
                        aria-invalid={!entry.original_term.trim()}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Tên chuẩn hoá</Label>
                      <Input
                        value={entry.canonical_form}
                        onChange={(e) => updateEntry(index, { canonical_form: e.target.value })}
                        placeholder="vd: Lý Phong"
                        className="h-7 text-xs"
                        aria-invalid={!entry.canonical_form.trim()}
                      />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 pl-6">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Loại</Label>
                    <Select
                      value={entry.entity_type}
                      onValueChange={(v) =>
                        updateEntry(index, { entity_type: v as GlossaryEntry["entity_type"] })
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
                        updateEntry(index, {
                          first_seen_chapter: e.target.value === "" ? null : Number(e.target.value),
                        })
                      }
                      placeholder="(tuỳ chọn)"
                      className="h-7 text-xs"
                    />
                  </div>
                </div>

                <div className="space-y-1 pl-6">
                  <Label className="text-xs text-muted-foreground">Ghi chú phát âm</Label>
                  <Input
                    value={entry.pronunciation_note ?? ""}
                    onChange={(e) =>
                      updateEntry(index, { pronunciation_note: e.target.value || null })
                    }
                    placeholder="(tuỳ chọn)"
                    className="h-7 text-xs"
                  />
                </div>

                {missingRequired && (
                  <p className="pl-6 text-[0.7rem] text-destructive">
                    Cần điền Tên gốc và Tên chuẩn hoá trước khi lưu.
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
