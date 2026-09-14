"use client";

import { useRef, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import TableToolbar from "@/components/TableToolbar";
import type { SaveController } from "@/components/SettingsSectionShell";

// 3 the duy nhat VieNeu-TTS ho tro chinh thuc (xem README "Emotion cues
// (experimental)" + data/emotion_lexicon.json._note) - hien thi lam goi y
// bam-de-them, khong ep buoc vi nguoi dung van co the tu go the khac de thu.
const SUGGESTED_TAGS = ["[cười]", "[thở dài]", "[hắng giọng]"];

interface Row {
  _id: number;
  label: string;
  tag: string;
}

interface Props {
  value: Record<string, string[]>;
  onChange: (next: Record<string, string[]>) => void;
  table: SaveController;
}

function rowsFromValue(value: Record<string, string[]>): Row[] {
  const rows: Row[] = [];
  let id = 0;
  for (const label of Object.keys(value)) {
    const tags = value[label] ?? [];
    if (tags.length === 0) rows.push({ _id: id++, label, tag: "" });
    else for (const tag of tags) rows.push({ _id: id++, label, tag });
  }
  return rows;
}

function rowsToValue(rows: Row[]): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const { label, tag } of rows) {
    const key = label.trim();
    if (!key) continue;
    if (!(key in out)) out[key] = [];
    const t = tag.trim();
    if (t && !out[key].includes(t)) out[key].push(t);
  }
  return out;
}

// 2026-09-15 - Truoc day day la 1 danh sach The (Card) theo TUNG nhan cam
// xuc, moi Card co: 1 nut Xoa nhan rieng, 1 o nhap + nut Them-tu RIENG, va
// tung tu/the ben trong lai co 1 nut X rieng de xoa - qua nhieu bo nut Them/
// Xoa lap lai, chi hop ly khi so nhan/tu con it (dung yeu cau nguoi dung can
// sua). Gio GOM PHANG (flatten) thanh 1 BANG duy nhat, moi dong la 1 cap
// (nhan, tu/the) - 1 nhan co N tu se la N dong CUNG nhan do; nhan chua co tu
// nao la 1 dong voi o "Tu/the" rong. Them/Xoa/Luu dung chung 1 TableToolbar
// (xem TableToolbar.tsx) cho CA nhan lan tu, khong con phan biet 2 co che
// rieng nua - xoa dong cuoi cung cua 1 nhan tuong duong xoa ca nhan do.
//
// `_id` la state NOI BO on dinh (khong phai chinh "nhan"/"tu" lam id) vi
// nguoi dung dang go dep nhan/tu co the trung/rong tam thoi luc them dong
// moi - dung chuoi dang go lam id se gay xung dot React key/mat selection.
export default function EmotionLexiconEditor({ value, onChange, table }: Props) {
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

  function addRow(prefill?: Partial<Row>) {
    const row: Row = { _id: nextId.current++, label: "", tag: "", ...prefill };
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

  const usedTags = new Set(rows.map((r) => r.tag).filter(Boolean));
  const suggestions = SUGGESTED_TAGS.filter((t) => !usedTags.has(t));

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Mỗi dòng là 1 cặp Nhãn → Từ/thẻ mà Beta sẽ chọn 1 khi chèn (1 nhãn có thể có nhiều dòng).
        Sửa từ/thẻ của 1 nhãn có sẵn có hiệu lực ngay sau khi lưu; <strong>thêm hoặc xoá cả một
        nhãn (xoá hết các dòng của nhãn đó) cần khởi động lại backend</strong> mới có hiệu lực với
        Alpha/Beta.
      </p>

      <TableToolbar
        totalCount={rows.length}
        selectedCount={selected.size}
        onToggleAll={toggleAll}
        onAdd={() => addRow()}
        addLabel="Thêm dòng"
        onDeleteSelected={deleteSelected}
        onSave={table.save}
        saving={table.status === "saving"}
        error={table.error}
      />

      {suggestions.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Gợi ý đã xác minh:</span>
          {suggestions.map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => addRow({ tag })}
              className="rounded-full border border-dashed px-2 py-0.5 font-mono text-[0.7rem] text-muted-foreground hover:bg-muted"
            >
              + {tag}
            </button>
          ))}
        </div>
      )}

      {rows.length === 0 && (
        <p className="text-xs italic text-muted-foreground">Chưa có nhãn cảm xúc nào.</p>
      )}

      <div className="space-y-1.5">
        {rows.length > 0 && (
          <div className="flex items-center gap-2 px-1 text-[0.7rem] text-muted-foreground">
            <span className="w-4 shrink-0" />
            <span className="w-36 shrink-0">Nhãn</span>
            <span className="flex-1">Từ / thẻ</span>
          </div>
        )}
        {rows.map((row) => (
          <div key={row._id} className="flex items-center gap-2 rounded-lg border p-2">
            <Checkbox
              checked={selected.has(row._id)}
              onCheckedChange={(checked) => toggleRow(row._id, checked === true)}
              aria-label={`Chọn dòng ${row.label || "mới"}`}
              className="shrink-0"
            />
            <Input
              value={row.label}
              onChange={(e) => updateRow(row._id, { label: e.target.value })}
              placeholder="vd: gian_du"
              className="h-7 w-36 shrink-0 font-mono text-xs"
              aria-invalid={!row.label.trim()}
            />
            <Input
              value={row.tag}
              onChange={(e) => updateRow(row._id, { tag: e.target.value })}
              placeholder="(để trống nếu nhãn chưa có từ)"
              className="h-7 flex-1 font-mono text-xs"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
