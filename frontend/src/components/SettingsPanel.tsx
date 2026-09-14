"use client";

import { useEffect, useState, type ReactNode } from "react";
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
import EmotionLexiconEditor from "@/components/EmotionLexiconEditor";
import GlossaryEditor from "@/components/GlossaryEditor";
import LiveGlossaryManager from "@/components/LiveGlossaryManager";
import PunctuationPauseEditor from "@/components/PunctuationPauseEditor";
import type { GlossaryEntry } from "@/lib/types";

type SettingsKey = "emotion-lexicon" | "glossary-seed" | "punctuation-pauses";

// Ca 3 file du lieu deu mang theo metadata "_placeholder"/"_note" (xem
// data/*.json) - khong hien thi cho nguoi dung sua nhung PHAI giu nguyen khi
// luu lai, khong thi mat ghi chu goc cua team.
function isMetaKey(key: string) {
  return key.startsWith("_");
}

function metaOf(raw: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(raw).filter(([k]) => isMetaKey(k)));
}

// Chrome chung (tai/luu/dong/trang thai loi) cho ca 3 khoi cai dat - moi khoi
// chi khac nhau o kieu du lieu T va giao dien sua T (children render-prop),
// thay vi lap lai textarea + JSON.parse/stringify nhu truoc (khong than thien
// nguoi dung khong ranh JSON).
function SettingsSectionShell<T>({
  label,
  hint,
  settingsKey,
  toContent,
  toRaw,
  validate,
  children,
}: {
  label: string;
  hint: string;
  settingsKey: SettingsKey;
  toContent: (raw: Record<string, unknown>) => T;
  toRaw: (content: T, raw: Record<string, unknown>) => Record<string, unknown>;
  validate?: (content: T) => string | null;
  children: (content: T, setContent: (next: T) => void) => ReactNode;
}) {
  const [raw, setRaw] = useState<Record<string, unknown> | null>(null);
  const [content, setContent] = useState<T | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "saving" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const data = await fetchSettingsFile(settingsKey);
      setRaw(data);
      setContent(toContent(data));
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tải thất bại");
      setStatus("error");
    }
  }

  async function save() {
    if (content === null) return;
    const validationError = validate?.(content) ?? null;
    if (validationError) {
      setError(validationError);
      setStatus("error");
      return;
    }
    setStatus("saving");
    setError(null);
    try {
      await uploadSettingsFile(settingsKey, toRaw(content, raw ?? {}));
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại");
      setStatus("error");
    }
  }

  function close() {
    setRaw(null);
    setContent(null);
    setStatus("idle");
    setError(null);
  }

  return (
    <div className="space-y-2 border-t pt-4 first:border-t-0 first:pt-0">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        {content === null && (
          <Button size="sm" variant="outline" onClick={load} disabled={status === "loading"}>
            {status === "loading" ? "Đang tải..." : "Tải để sửa"}
          </Button>
        )}
      </div>
      {content !== null && (
        <div className="space-y-3">
          {children(content, setContent)}
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={save} disabled={status === "saving"}>
              {status === "saving" ? "Đang lưu..." : "Lưu"}
            </Button>
            <Button size="sm" variant="ghost" onClick={close}>
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

          <SettingsSectionShell<GlossaryEntry[]>
            label="Glossary khởi tạo"
            hint="Danh sách entry ban đầu cho Character/Terminology Glossary (nạp vào ChromaDB khi pipeline khởi động)."
            settingsKey="glossary-seed"
            toContent={(raw) => (Array.isArray(raw.entries) ? (raw.entries as GlossaryEntry[]) : [])}
            toRaw={(content, raw) => ({ ...metaOf(raw), entries: content })}
            validate={(content) =>
              content.some((e) => !e.original_term.trim() || !e.canonical_form.trim())
                ? "Có entry còn thiếu Tên gốc hoặc Tên chuẩn hoá."
                : null
            }
          >
            {(content, setContent) => <GlossaryEditor value={content} onChange={setContent} />}
          </SettingsSectionShell>

          <LiveGlossaryManager />

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
