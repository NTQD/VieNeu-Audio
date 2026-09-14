"use client";

import { Tabs, TabsList, TabsPanel, TabsTab } from "@/components/ui/tabs";
import DataViewerDialog from "@/components/DataViewerDialog";
import { SettingsSectionShell } from "@/components/SettingsSectionShell";
import GlossaryEditor from "@/components/GlossaryEditor";
import LiveGlossaryManager from "@/components/LiveGlossaryManager";
import type { GlossaryEntry } from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// 2026-09-14 - Tach rieng thanh 1 popup LON HON, DOC LAP voi "Cai dat du
// lieu" (yeu cau nguoi dung: 2 khoi Glossary chiem het khong gian cua popup
// chung, va "khong co su khac biet" ro rang giua Glossary khoi tao/dang dung
// khi ca 2 chi la 2 khoi xep chong trong CUNG 1 danh sach dai). Gop lai
// thanh 1 dialog rieng, kieu TAB - "Khởi tạo" (sua file JSON tinh
// data/glossary_seed.json) va "Đang dùng" (doc/ghi truc tiep ChromaDB, xem
// LiveGlossaryManager.tsx) - ro rang la 2 CHE DO xem/sua khac nhau cua CUNG
// 1 khai niem Glossary, thay vi 2 muc khong lien quan trong 1 danh sach.
//
// FULLY CONTROLLED (open/onOpenChange tu SettingsPanel.tsx, khong con tu
// quan ly trigger/state noi bo) - xem DataViewerDialog.tsx de biet ly do:
// long 1 Dialog CON ben trong DialogContent cua dialog "Cai dat du lieu" se
// khien no bi unmount THEO khi dialog cha dong, du dang o trang thai
// open=true rieng - phai render nhu ANH EM (sibling), khong long vao nhau.
export default function GlossaryManagerDialog({ open, onOpenChange }: Props) {
  return (
    <DataViewerDialog open={open} onOpenChange={onOpenChange} title="Quản lý Glossary">
      <Tabs defaultValue="live">
        <TabsList>
          <TabsTab value="live">Đang dùng (thời gian thực)</TabsTab>
          <TabsTab value="seed">Khởi tạo</TabsTab>
        </TabsList>

        <TabsPanel value="live">
          <LiveGlossaryManager />
        </TabsPanel>

        <TabsPanel value="seed">
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Danh sách entry ban đầu cho Character/Terminology Glossary (nạp vào ChromaDB khi
              pipeline khởi động). Sửa file này KHÔNG ảnh hưởng tới các entry đã có trong ChromaDB
              (xem tab &ldquo;Đang dùng&rdquo;) — chỉ áp dụng cho lần khởi động tiếp theo.
            </p>
            <SettingsSectionShell<GlossaryEntry[]>
              settingsKey="glossary-seed"
              toContent={(raw) => (Array.isArray(raw.entries) ? (raw.entries as GlossaryEntry[]) : [])}
              toRaw={(content, raw) => ({
                ...Object.fromEntries(Object.entries(raw).filter(([k]) => k.startsWith("_"))),
                entries: content,
              })}
              validate={(content) =>
                content.some((e) => !e.original_term.trim() || !e.canonical_form.trim())
                  ? "Có entry còn thiếu Tên gốc hoặc Tên chuẩn hoá."
                  : null
              }
            >
              {(content, setContent, table) => (
                <GlossaryEditor value={content} onChange={setContent} table={table} />
              )}
            </SettingsSectionShell>
          </div>
        </TabsPanel>
      </Tabs>
    </DataViewerDialog>
  );
}
