"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsPanel, TabsTab } from "@/components/ui/tabs";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "cn";
import { SettingsSectionShell } from "@/components/SettingsSectionShell";
import GlossaryEditor from "@/components/GlossaryEditor";
import LiveGlossaryManager from "@/components/LiveGlossaryManager";
import type { GlossaryEntry } from "@/lib/types";

// 2026-09-14 - Tach rieng thanh 1 popup LON HON, DOC LAP voi "Cai dat du
// lieu" (yeu cau nguoi dung: 2 khoi Glossary chiem het khong gian cua popup
// chung, va "khong co su khac biet" ro rang giua Glossary khoi tao/dang dung
// khi ca 2 chi la 2 khoi xep chong trong CUNG 1 danh sach dai). Gop lai
// thanh 1 dialog rieng, kieu TAB - "Khởi tạo" (sua file JSON tinh
// data/glossary_seed.json) va "Đang dùng" (doc/ghi truc tiep ChromaDB, xem
// LiveGlossaryManager.tsx) - ro rang la 2 CHE DO xem/sua khac nhau cua CUNG
// 1 khai niem Glossary, thay vi 2 muc khong lien quan trong 1 danh sach.
export default function GlossaryManagerDialog() {
  return (
    <Dialog>
      <DialogTrigger className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
        Quản lý Glossary
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Quản lý Glossary</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="live">
          <TabsList>
            <TabsTab value="live">Đang dùng (thời gian thực)</TabsTab>
            <TabsTab value="seed">Khởi tạo</TabsTab>
          </TabsList>

          <TabsPanel value="live">
            <LiveGlossaryManager />
          </TabsPanel>

          <TabsPanel value="seed">
            <SettingsSectionShell<GlossaryEntry[]>
              label="Glossary khởi tạo"
              hint="Danh sách entry ban đầu cho Character/Terminology Glossary (nạp vào ChromaDB khi pipeline khởi động). Sửa file này KHÔNG ảnh hưởng tới các entry đã có trong ChromaDB (xem tab 'Đang dùng') — chỉ áp dụng cho lần khởi động tiếp theo."
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
              {(content, setContent) => <GlossaryEditor value={content} onChange={setContent} />}
            </SettingsSectionShell>
          </TabsPanel>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
