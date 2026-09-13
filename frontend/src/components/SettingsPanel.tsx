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
import { fetchSettingsFile, getStoredApiKey, setStoredApiKey, uploadSettingsFile } from "@/lib/api";

type SettingsKey = "emotion-lexicon" | "glossary-seed" | "punctuation-pauses";

const SECTIONS: { key: SettingsKey; label: string; hint: string }[] = [
  {
    key: "emotion-lexicon",
    label: "Từ điển cảm xúc",
    hint: "emotion_label -> danh sách từ ứng viên. Alpha dùng tập nhãn (key) để gắn cờ, Beta chọn 1 từ trong danh sách khi chèn.",
  },
  {
    key: "glossary-seed",
    label: "Glossary khởi tạo",
    hint: "Danh sách entry ban đầu cho Character/Terminology Glossary (nạp vào ChromaDB khi pipeline khởi động).",
  },
  {
    key: "punctuation-pauses",
    label: "Bảng ngắt nghỉ theo dấu câu",
    hint: "dấu câu -> độ dài khoảng lặng (ms). Dùng cho ngắt nghỉ ngắn bên trong 1 đoạn (Section 7.3).",
  },
];

function SettingsSection({ section }: { section: (typeof SECTIONS)[number] }) {
  const [text, setText] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "saving" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const data = await fetchSettingsFile(section.key);
      setText(JSON.stringify(data, null, 2));
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tải thất bại");
      setStatus("error");
    }
  }

  async function save() {
    if (text === null) return;
    setStatus("saving");
    setError(null);
    try {
      const parsed = JSON.parse(text);
      await uploadSettingsFile(section.key, parsed);
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "JSON không hợp lệ hoặc lưu thất bại");
      setStatus("error");
    }
  }

  return (
    <div className="space-y-2 border-t pt-4 first:border-t-0 first:pt-0">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{section.label}</p>
          <p className="text-xs text-muted-foreground">{section.hint}</p>
        </div>
        {text === null && (
          <Button size="sm" variant="outline" onClick={load} disabled={status === "loading"}>
            {status === "loading" ? "Đang tải..." : "Tải để sửa"}
          </Button>
        )}
      </div>
      {text !== null && (
        <div className="space-y-2">
          <textarea
            className="w-full h-40 rounded-md border bg-background p-2 font-mono text-xs"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={save} disabled={status === "saving"}>
              {status === "saving" ? "Đang lưu..." : "Lưu (ghi đè toàn bộ file)"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setText(null)}>
              Đóng
            </Button>
          </div>
        </div>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
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
  return (
    <Dialog>
      <DialogTrigger className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
        Cài đặt dữ liệu
      </DialogTrigger>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Cài đặt dữ liệu & API key</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {SECTIONS.map((section) => (
            <SettingsSection key={section.key} section={section} />
          ))}

          <ByokSection />
        </div>
      </DialogContent>
    </Dialog>
  );
}
