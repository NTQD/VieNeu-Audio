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
import EmotionLexiconEditor from "@/components/EmotionLexiconEditor";
import GlossaryManagerDialog from "@/components/GlossaryManagerDialog";
import PunctuationPauseEditor from "@/components/PunctuationPauseEditor";

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
  return (
    <Dialog>
      <DialogTrigger className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
        Cài đặt dữ liệu
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Cài đặt dữ liệu & API key</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <SettingsSectionShell<Record<string, string[]>>
            label="Từ điển cảm xúc"
            hint="emotion_label -> danh sách từ ứng viên. Alpha dùng tập nhãn (key) để gắn cờ, Beta chọn 1 từ trong danh sách khi chèn."
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
            {(content, setContent) => (
              <EmotionLexiconEditor value={content} onChange={setContent} />
            )}
          </SettingsSectionShell>

          {/* 2026-09-14 - gop "Glossary khoi tao" + "Glossary dang dung" thanh
              1 popup RIENG, lon hon, kieu tab (xem GlossaryManagerDialog.tsx) -
              yeu cau nguoi dung: 2 khoi Glossary xep chong truoc day chiem het
              khong gian cua popup Cai dat du lieu, va khong ro rang la 2 CHE
              DO xem/sua khac nhau cua cung 1 khai niem thay vi 2 muc doc lap. */}
          <div className="space-y-2 border-t pt-4 first:border-t-0 first:pt-0">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Glossary</p>
                <p className="text-xs text-muted-foreground">
                  Character/Terminology Glossary — danh sách khởi tạo (file JSON tĩnh) và bảng đang
                  dùng thời gian thực (ChromaDB), quản lý trong 1 cửa sổ riêng.
                </p>
              </div>
              <GlossaryManagerDialog />
            </div>
          </div>

          <SettingsSectionShell<Record<string, number>>
            label="Bảng ngắt nghỉ theo dấu câu"
            hint="dấu câu -> độ dài khoảng lặng (ms). Dùng cho ngắt nghỉ ngắn bên trong 1 đoạn (Section 7.3)."
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
            {(content, setContent) => (
              <PunctuationPauseEditor value={content} onChange={setContent} />
            )}
          </SettingsSectionShell>

          <ByokSection />
        </div>
      </DialogContent>
    </Dialog>
  );
}
