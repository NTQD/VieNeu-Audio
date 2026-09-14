"use client";

import { useEffect, useRef, useState } from "react";
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

interface Row {
  _id: number;
  entry: GlossaryEntry;
  // true = dong nay CHUA TUNG duoc luu vao ChromaDB (them qua nut "Them" -
  // Ten goc con sua duoc, la doc-id chua chot). false = da co trong ChromaDB,
  // Ten goc khoa lai (doc id, doi ten = xoa+tao moi, ngoai pham vi bang nay).
  isNew: boolean;
}

// 2026-09-14 - "Glossary dang dung": doc/ghi TRUC TIEP tren ChromaDB qua
// GET/POST/DELETE /api/glossary - KHAC voi "Glossary khoi tao" o tren
// (GlossaryEditor.tsx, sua file JSON tinh data/glossary_seed.json).
//
// 2026-09-15 - Truoc day moi The (Card) tu quan ly nut Luu/Xoa RIENG cua no
// (goi upsert/delete tung entry 1), cong 1 The "Them thuat ngu moi" RIENG BIET
// o duoi voi bo input/nut Them cua chinh no - 3 co che khac nhau cho 3 muc
// dich. Yeu cau nguoi dung: dong bo giao dien voi Glossary khoi tao/Tu dien
// cam xuc/Bang ngat nghi (TableToolbar dung chung). ChromaDB khong co endpoint
// luu/xoa HANG LOAT, nen "Luu"/"Xoa da chon" o day goi NHIEU request don le
// (upsert/delete tung entry, Promise.allSettled) thay vi 1 request thay-the-
// toan-bo nhu 3 bang JSON kia - ve UI/hanh vi nguoi dung thi giong het (1
// checkbox chon dong, 1 nut Them, 1 nut Xoa da chon, 1 nut Luu DUY NHAT), chi
// khac o tang goi API ben duoi.
export default function LiveGlossaryManager() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const nextId = useRef(0);
  // Nhan da CHON THU CONG cho dong nao (Select's onValueChange) - goi y tu
  // dong (bat dong bo, den SAU) se bo qua dong do de khong ghi de lua chon.
  const labelManuallySet = useRef<Set<number>>(new Set());
  const suggestDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setError(null);
    fetchLiveGlossaryEntries()
      .then((data) => {
        if (cancelled) return;
        const initial = data.map((entry) => ({ _id: nextId.current++, entry, isNew: false }));
        setRows(initial);
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
  }, []);

  useEffect(() => {
    return () => {
      if (suggestDebounce.current) clearTimeout(suggestDebounce.current);
    };
  }, []);

  function updateRow(id: number, patch: Partial<GlossaryEntry>) {
    setRows((prev) =>
      prev ? prev.map((r) => (r._id === id ? { ...r, entry: { ...r.entry, ...patch } } : r)) : prev
    );
  }

  function handleTermChange(id: number, term: string) {
    updateRow(id, { original_term: term });
    labelManuallySet.current.delete(id);
    if (suggestDebounce.current) clearTimeout(suggestDebounce.current);
    if (!term.trim()) return;
    suggestDebounce.current = setTimeout(async () => {
      try {
        const suggested = await suggestGlossaryLabel(term);
        if (labelManuallySet.current.has(id)) return;
        setRows((prev) =>
          prev
            ? prev.map((r) =>
                r._id === id && r.entry.original_term === term
                  ? { ...r, entry: { ...r.entry, entity_type: suggested } }
                  : r
              )
            : prev
        );
      } catch {
        // Goi y chi la tien ich phu - loi o day khong can bao.
      }
    }, 400);
  }

  function addRow() {
    setRows((prev) => [...(prev ?? []), { _id: nextId.current++, entry: blankEntry(), isNew: true }]);
  }

  function toggleAll(checked: boolean) {
    setSelected(checked && rows ? new Set(rows.map((r) => r._id)) : new Set());
  }

  function toggleRow(id: number, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  async function deleteSelected() {
    if (!rows) return;
    const toDelete = rows.filter((r) => selected.has(r._id));
    const persisted = toDelete.filter((r) => !r.isNew);
    setError(null);
    const results = await Promise.allSettled(
      persisted.map((r) => deleteLiveGlossaryEntry(r.entry.original_term))
    );
    const failedIds = new Set<number>();
    results.forEach((res, i) => {
      if (res.status === "rejected") failedIds.add(persisted[i]._id);
    });
    if (failedIds.size > 0) {
      setError(`Xoá thất bại ${failedIds.size} entry — thử lại.`);
    }
    setRows((prev) => (prev ? prev.filter((r) => !selected.has(r._id) || failedIds.has(r._id)) : prev));
    setSelected(failedIds);
  }

  async function saveAll() {
    if (!rows) return;
    const missing = rows.some((r) => !r.entry.original_term.trim() || !r.entry.canonical_form.trim());
    if (missing) {
      setError("Có entry còn thiếu Tên gốc hoặc Tên chuẩn hoá.");
      return;
    }
    setSaving(true);
    setError(null);
    const results = await Promise.allSettled(rows.map((r) => upsertLiveGlossaryEntry(r.entry)));
    const failedIds = new Set<number>();
    results.forEach((res, i) => {
      if (res.status === "rejected") failedIds.add(rows[i]._id);
    });
    setRows((prev) =>
      prev ? prev.map((r) => (failedIds.has(r._id) ? r : { ...r, isNew: false })) : prev
    );
    setSaving(false);
    if (failedIds.size > 0) setError(`Lưu thất bại ${failedIds.size} entry — thử lại.`);
  }

  if (rows === null) {
    return (
      <p className="text-sm text-muted-foreground">
        {status === "error" ? (error ?? "Tải thất bại") : "Đang tải..."}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Đọc/ghi trực tiếp trên ChromaDB — nơi các thuật ngữ đã &ldquo;Duyệt&rdquo; (từ popup
        &ldquo;Thuật ngữ mới phát hiện&rdquo;) thực sự được lưu. Khác với tab &ldquo;Khởi
        tạo&rdquo;, chỉ là file seed tĩnh nạp 1 lần lúc pipeline khởi động.
      </p>

      <TableToolbar
        totalCount={rows.length}
        selectedCount={selected.size}
        onToggleAll={toggleAll}
        onAdd={addRow}
        addLabel="Thêm entry"
        onDeleteSelected={deleteSelected}
        onSave={saveAll}
        saving={saving}
        error={error}
      />

      {rows.length === 0 && (
        <p className="text-xs italic text-muted-foreground">
          Glossary đang dùng chưa có entry nào (chưa có thuật ngữ nào được duyệt).
        </p>
      )}

      <div className="space-y-2">
        {rows.map((row) => {
          const { entry } = row;
          const missingRequired = !entry.original_term.trim() || !entry.canonical_form.trim();
          return (
            <Card key={row._id} size="sm">
              <CardContent className="space-y-2">
                <div className="flex items-start gap-2">
                  <Checkbox
                    checked={selected.has(row._id)}
                    onCheckedChange={(checked) => toggleRow(row._id, checked === true)}
                    aria-label={`Chọn entry ${entry.original_term || "mới"}`}
                    className="mt-1.5 shrink-0"
                  />
                  <div className="grid flex-1 grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Tên gốc</Label>
                      <Input
                        value={entry.original_term}
                        disabled={!row.isNew}
                        onChange={(e) => handleTermChange(row._id, e.target.value)}
                        placeholder="vd: Huyết Nguyệt Tông"
                        className="h-7 text-xs"
                        aria-invalid={!entry.original_term.trim()}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Tên chuẩn hoá</Label>
                      <Input
                        value={entry.canonical_form}
                        onChange={(e) => updateRow(row._id, { canonical_form: e.target.value })}
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
                      onValueChange={(v) => {
                        labelManuallySet.current.add(row._id);
                        updateRow(row._id, { entity_type: v as GlossaryEntry["entity_type"] });
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
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Xuất hiện từ chương</Label>
                    <Input
                      type="number"
                      min={1}
                      value={entry.first_seen_chapter ?? ""}
                      onChange={(e) =>
                        updateRow(row._id, {
                          first_seen_chapter: e.target.value === "" ? null : Number(e.target.value),
                        })
                      }
                      placeholder="(tuỳ chọn)"
                      className="h-7 text-xs"
                    />
                  </div>
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
