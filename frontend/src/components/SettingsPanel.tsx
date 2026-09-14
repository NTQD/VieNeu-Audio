"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button, buttonVariants } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "cn";
import { getStoredApiKey, setStoredApiKey } from "@/lib/api";
import { isMetaKey, metaOf, SettingsSectionShell } from "@/components/SettingsSectionShell";
import DataViewerDialog from "@/components/DataViewerDialog";
import EmotionLexiconEditor from "@/components/EmotionLexiconEditor";
import GlossaryManagerDialog from "@/components/GlossaryManagerDialog";
import PunctuationPauseEditor from "@/components/PunctuationPauseEditor";

// Row "tieu de + mo ta + nut mo dialog du lieu lon" dung chung cho ca 3 khu
// vuc du lieu - tach rieng de khong lap code 3 lan, va de bao dam ca 3 trong
// GIONG HET nhau (cung khoang cach/kieu chu). Nut o day chi la <Button>
// THUONG (khong phai DialogTrigger) - xem SettingsPanel() de biet ly do:
// dialog du lieu lon KHONG con long ben trong dialog nay nua, chi con 1
// nut goi callback mo/dong state o cap cha.
function DataSectionRow({
  title,
  hint,
  buttonLabel,
  onClick,
}: {
  title: string;
  hint: string;
  buttonLabel: string;
  onClick: () => void;
}) {
  return (
    <div className="space-y-2 border-t pt-4 first:border-t-0 first:pt-0">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        <Button size="sm" variant="outline" onClick={onClick} className="shrink-0">
          {buttonLabel}
        </Button>
      </div>
    </div>
  );
}

// BYOK - moi nguoi dung tu nhap Gemini API key rieng cua ho (quyet dinh chot
// 2026-09-10: "users will use their own API key, we use their key for their
// own use"). Luu O TRINH DUYET (localStorage) - khong gui/luu server-side lau
// dai, chi gui kem 1 lan trong body cua POST /api/submit (KHONG bao gio qua
// query string) va backend chi giu tam trong bo nho theo job (xem
// backend/app/main.py). Phu hop pham vi demo/beta vai nguoi dung than quen,
// khong phai co che luu tru bi mat cap san xuat.
function ByokSection() {
  const [key, setKey] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setKey(getStoredApiKey());
  }, []);

  function handleSave() {
    setStoredApiKey(key);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  function handleClear() {
    setKey("");
    setStoredApiKey("");
  }

  return (
    <div className="space-y-1.5 border-t pt-4">
      <Label htmlFor="byok-key">Gemini API key riêng (BYOK)</Label>
      <input
        id="byok-key"
        type="password"
        placeholder="Dán API key Gemini của bạn (aistudio.google.com/apikey)"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        className="block w-full rounded-md border bg-background px-3 py-1.5 text-sm"
      />
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={handleSave}>
          {saved ? "Đã lưu" : "Lưu key"}
        </Button>
        <Button size="sm" variant="ghost" onClick={handleClear}>
          Xoá key
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Key chỉ lưu trên trình duyệt của bạn (localStorage), không lưu lại trên server — mỗi lần
        bấm &ldquo;Bắt đầu xử lý&rdquo;, key được gửi kèm để backend gọi Gemini bằng đúng tài
        khoản của bạn. Để trống thì dùng key mặc định của server (nếu có).
      </p>
    </div>
  );
}

export default function SettingsPanel() {
  // Dialog "Cai dat du lieu" + ca 3 dialog du lieu lon (Tu dien cam xuc/
  // Glossary/Bang ngat nghi) deu la state RIENG, quan ly CUNG 1 CAP
  // (SettingsPanel) - XAC NHAN CO THAT qua kiem tra truc tiep DOM
  // (2026-09-14): ban dau 3 dialog lon nay duoc render LONG BEN TRONG
  // <DialogContent> cua dialog "Cai dat du lieu" (xem DataViewerDialog.tsx
  // de biet chi tiet loi). Khi dialog cha dong va Base UI thao Popup cua no
  // khoi DOM sau animation-out, CA CAY CON (ke ca dialog du lieu vua duoc
  // mo) bi go theo - React Portal van gan voi cay SO HUU, khong phai vi tri
  // DOM. Fix: ca 4 dialog o day deu la ANH EM (sibling) trong cung 1
  // Fragment, KHONG dialog nao long ben trong dialog khac.
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [emotionOpen, setEmotionOpen] = useState(false);
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const [pauseOpen, setPauseOpen] = useState(false);

  function openChild(setChildOpen: (v: boolean) => void) {
    setSettingsOpen(false);
    setChildOpen(true);
  }

  return (
    <>
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogTrigger className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
          Cài đặt dữ liệu
        </DialogTrigger>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Cài đặt dữ liệu & API key</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <DataSectionRow
              title="Từ điển cảm xúc"
              hint="emotion_label -> danh sách từ ứng viên. Alpha dùng tập nhãn (key) để gắn cờ, Beta chọn 1 từ trong danh sách khi chèn."
              buttonLabel="Xem/Sửa"
              onClick={() => openChild(setEmotionOpen)}
            />

            {/* 2026-09-14 - gop "Glossary khoi tao" + "Glossary dang dung" thanh
                1 popup RIENG, lon hon, kieu tab (xem GlossaryManagerDialog.tsx) -
                yeu cau nguoi dung: 2 khoi Glossary xep chong truoc day chiem het
                khong gian cua popup Cai dat du lieu, va khong ro rang la 2 CHE
                DO xem/sua khac nhau cua cung 1 khai niem thay vi 2 muc doc lap. */}
            <DataSectionRow
              title="Glossary"
              hint="Character/Terminology Glossary — danh sách khởi tạo (file JSON tĩnh) và bảng đang dùng thời gian thực (ChromaDB), quản lý trong 1 cửa sổ riêng."
              buttonLabel="Quản lý Glossary"
              onClick={() => openChild(setGlossaryOpen)}
            />

            <DataSectionRow
              title="Bảng ngắt nghỉ theo dấu câu"
              hint="dấu câu -> độ dài khoảng lặng (ms). Dùng cho ngắt nghỉ ngắn bên trong 1 đoạn (Section 7.3)."
              buttonLabel="Xem/Sửa"
              onClick={() => openChild(setPauseOpen)}
            />

            <ByokSection />
          </div>
        </DialogContent>
      </Dialog>

      <DataViewerDialog
        open={emotionOpen}
        onOpenChange={setEmotionOpen}
        title="Từ điển cảm xúc"
        description="emotion_label -> danh sách từ ứng viên. Alpha dùng tập nhãn (key) để gắn cờ, Beta chọn 1 từ trong danh sách khi chèn."
      >
        <SettingsSectionShell<Record<string, string[]>>
          settingsKey="emotion-lexicon"
          toContent={(raw) => {
            const content: Record<string, string[]> = {};
            for (const [k, v] of Object.entries(raw)) {
              if (!isMetaKey(k) && Array.isArray(v)) content[k] = v as string[];
            }
            return content;
          }}
          toRaw={(content, raw) => ({ ...metaOf(raw), ...content })}
        >
          {(content, setContent, table) => (
            <EmotionLexiconEditor value={content} onChange={setContent} table={table} />
          )}
        </SettingsSectionShell>
      </DataViewerDialog>

      <GlossaryManagerDialog open={glossaryOpen} onOpenChange={setGlossaryOpen} />

      <DataViewerDialog
        open={pauseOpen}
        onOpenChange={setPauseOpen}
        title="Bảng ngắt nghỉ theo dấu câu"
        description="dấu câu -> độ dài khoảng lặng (ms). Dùng cho ngắt nghỉ ngắn bên trong 1 đoạn (Section 7.3)."
      >
        <SettingsSectionShell<Record<string, number>>
          settingsKey="punctuation-pauses"
          toContent={(raw) => {
            const content: Record<string, number> = {};
            for (const [k, v] of Object.entries(raw)) {
              if (!isMetaKey(k) && typeof v === "number") content[k] = v;
            }
            return content;
          }}
          toRaw={(content, raw) => ({ ...metaOf(raw), ...content })}
        >
          {(content, setContent, table) => (
            <PunctuationPauseEditor value={content} onChange={setContent} table={table} />
          )}
        </SettingsSectionShell>
      </DataViewerDialog>
    </>
  );
}
