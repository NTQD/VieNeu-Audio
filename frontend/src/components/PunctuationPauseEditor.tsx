"use client";

import { useRef, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import TableToolbar from "@/components/TableToolbar";
import type { SaveController } from "@/components/SettingsSectionShell";

const MAX_MS = 1000;

interface Row {
  _id: number;
  key: string;
  ms: number;
}

interface Props {
  value: Record<string, number>;
  onChange: (next: Record<string, number>) => void;
  table: SaveController;
}

function rowsFromValue(value: Record<string, number>): Row[] {
  return Object.entries(value).map(([key, ms], i) => ({ _id: i, key, ms }));
}

function rowsToValue(rows: Row[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of rows) {
    const key = row.key.trim();
    if (!key) continue;
    out[key] = row.ms;
  }
  return out;
}

// 2026-09-15 - Chuyen tu "1 dong = 1 key co san trong `value` + nut Xoa rieng
// tren tung dong, cong 1 form Them RIENG biet nam duoi bang" sang 1 bang co
// STATE HANG NOI BO (_id on dinh, khong phai key chuoi - vi key dang duoc
// go do nguoi dung co the trung/rong tam thoi trong luc them dong moi) +
// checkbox chon dong + TableToolbar dung chung (xem TableToolbar.tsx). Dong
// moi them qua nut "Them" gio la 1 dong TRONG ngay trong bang, sua truc tiep
// tai cho - khong con 2 co che Them khac nhau (1 o day, 1 nam duoi bang).
export default function PunctuationPauseEditor({ value, onChange, table }: Props) {
  const [rows, setRows] = useState<Row[]>(() => rowsFromValue(value));
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const nextId = useRef(rows.length);

  function commit(next: Row[]) {
    setRows(next);
    onChange(rowsToValue(next));
  }

  function updateRow(id: number, patch: Partial<Row>) {
    commit(rows.map((r) => (r._id === id ? { ...r, ...patch } : r)));
  }

  function addRow() {
    const row: Row = { _id: nextId.current++, key: "", ms: 200 };
    commit([...rows, row]);
  }

  function deleteSelected() {
    commit(rows.filter((r) => !selected.has(r._id)));
    setSelected(new Set());
  }

  function toggleAll(checked: boolean) {
    setSelected(checked ? new Set(rows.map((r) => r._id)) : new Set());
  }

  function toggleRow(id: number, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Dấu câu (hoặc token đặc biệt) → độ dài khoảng lặng (ms). Dùng cho ngắt nghỉ ngắn bên trong
        1 đoạn. Có hiệu lực ngay khi lưu, không cần khởi động lại backend.
      </p>

      <TableToolbar
        totalCount={rows.length}
        selectedCount={selected.size}
        onToggleAll={toggleAll}
        onAdd={addRow}
        addLabel="Thêm dòng"
        onDeleteSelected={deleteSelected}
        onSave={table.save}
        saving={table.status === "saving"}
        error={table.error}
      />

      {rows.length === 0 && (
        <p className="text-xs italic text-muted-foreground">Chưa có mục nào.</p>
      )}

      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row._id} className="flex items-center gap-2 rounded-lg border p-2">
            <Checkbox
              checked={selected.has(row._id)}
              onCheckedChange={(checked) => toggleRow(row._id, checked === true)}
              aria-label={`Chọn dòng ${row.key || "mới"}`}
            />
            <Input
              value={row.key}
              onChange={(e) => updateRow(row._id, { key: e.target.value })}
              placeholder="Dấu câu / token (vd: ~)"
              className="h-7 w-28 shrink-0 font-mono text-xs"
              aria-invalid={!row.key.trim()}
            />
            <Slider
              min={0}
              max={MAX_MS}
              step={10}
              value={[row.ms]}
              onValueChange={(v) => updateRow(row._id, { ms: Math.max(0, Math.round(Array.isArray(v) ? v[0] : v)) })}
              className="flex-1"
            />
            <Input
              type="number"
              min={0}
              value={row.ms}
              onChange={(e) => updateRow(row._id, { ms: Math.max(0, Number(e.target.value) || 0) })}
              className="h-7 w-16 shrink-0 text-xs"
            />
            <span className="w-6 shrink-0 text-xs text-muted-foreground">ms</span>
          </div>
        ))}
      </div>
    </div>
  );
}
