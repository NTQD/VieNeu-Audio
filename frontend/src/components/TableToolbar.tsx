"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Plus, Trash2 } from "lucide-react";

// Thanh cong cu DUNG CHUNG cho ca bang du lieu (Tu dien cam xuc / Glossary /
// Bang ngat nghi) - THAY THE cho viec moi dong/the/nhan tu quan ly rieng nut
// Them/Xoa cua no. Truoc day: moi dong co 1 nut Xoa rieng (vd. 1 icon
// Trash2 tren tung Card), Tu dien cam xuc con co them 1 o nhap + nut Them
// RIENG cho tung nhan cam xuc - khong scale khi 1 bang co nhieu du lieu.
// Gio: 1 checkbox "chon tat ca" + 1 nut Them + 1 nut Xoa (chi xoa nhung dong
// da chon) + 1 nut Luu, DUY NHAT 1 lan cho ca bang, dung o moi noi (xem
// EmotionLexiconEditor/GlossaryEditor/PunctuationPauseEditor.tsx).
export default function TableToolbar({
  totalCount,
  selectedCount,
  onToggleAll,
  onAdd,
  addLabel = "Thêm",
  onDeleteSelected,
  onSave,
  saving,
  error,
}: {
  totalCount: number;
  selectedCount: number;
  onToggleAll: (checked: boolean) => void;
  onAdd: () => void;
  addLabel?: string;
  onDeleteSelected: () => void;
  onSave: () => void;
  saving: boolean;
  error?: string | null;
}) {
  const allSelected = totalCount > 0 && selectedCount === totalCount;
  const indeterminate = selectedCount > 0 && !allSelected;

  return (
    <div className="sticky top-0 z-10 -mx-4 mb-2 flex flex-wrap items-center gap-2 border-b bg-popover px-4 py-2 sm:-mx-0 sm:px-0">
      <Checkbox
        checked={allSelected}
        indeterminate={indeterminate}
        onCheckedChange={(checked) => onToggleAll(checked === true)}
        disabled={totalCount === 0}
        aria-label="Chọn tất cả"
      />
      <span className="text-xs text-muted-foreground">
        {selectedCount > 0 ? `Đã chọn ${selectedCount}/${totalCount}` : `${totalCount} mục`}
      </span>

      <div className="ml-auto flex items-center gap-1.5">
        <Button size="sm" variant="outline" onClick={onAdd}>
          <Plus /> {addLabel}
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={onDeleteSelected}
          disabled={selectedCount === 0}
        >
          <Trash2 /> Xoá{selectedCount > 0 ? ` (${selectedCount})` : ""}
        </Button>
        <Button size="sm" onClick={onSave} disabled={saving}>
          {saving ? "Đang lưu..." : "Lưu"}
        </Button>
      </div>

      {error && <p className="w-full text-xs text-destructive">{error}</p>}
    </div>
  );
}
