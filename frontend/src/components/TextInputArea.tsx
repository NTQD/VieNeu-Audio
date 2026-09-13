"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { countWords } from "@/lib/text-utils";

interface Props {
  value: string;
  onChange: (text: string) => void;
  disabled?: boolean;
}

// Drag-drop + paste (.txt/.docx) - Section 4 cua spec: "Unchanged from v3".
// Parse .docx THAT su la viec cua backend (python-docx, da co san server-side
// tu truoc) - o day chi doc truoc noi dung neu la .txt (hien thi ngay cho
// nguoi dung xem/sua), con .docx chi hien ten file + placeholder note vi
// khong parse .docx phia client.
export default function TextInputArea({ value, onChange, disabled }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  // True khi noi dung textarea hien tai la placeholder cua .docx (khong
  // phai van ban that) - dung de KHONG dem so tu cua cau placeholder gia
  // (2026-09-13, xem han che that o docstring tren: .docx chua duoc doc that
  // o phia client/server, chi hien placeholder cho toi khi gui di).
  const [isDocxPlaceholder, setIsDocxPlaceholder] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      setFileName(file.name);
      if (file.name.toLowerCase().endsWith(".txt")) {
        setIsDocxPlaceholder(false);
        const reader = new FileReader();
        reader.onload = () => onChange(String(reader.result ?? ""));
        reader.readAsText(file, "utf-8");
      } else if (file.name.toLowerCase().endsWith(".docx")) {
        setIsDocxPlaceholder(true);
        onChange(
          `[Đã tải "${file.name}" — nội dung .docx sẽ được trích xuất ở backend khi gửi đi]`,
        );
      }
    },
    [onChange],
  );

  const wordCount = useMemo(() => countWords(value), [value]);

  return (
    <div className="space-y-2">
      <Card
        className={`border-2 border-dashed p-6 text-center transition-colors ${
          isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          const file = e.dataTransfer.files?.[0];
          if (file) handleFile(file);
        }}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.docx"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
        <p className="text-sm text-muted-foreground">
          Kéo & thả file <span className="font-medium">.txt</span> hoặc{" "}
          <span className="font-medium">.docx</span> vào đây, hoặc bấm để chọn file
        </p>
        {fileName && (
          <p className="mt-1 text-xs text-muted-foreground">Đã chọn: {fileName}</p>
        )}
      </Card>

      <textarea
        className="w-full min-h-[220px] rounded-md border border-input bg-transparent p-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
        placeholder="...hoặc dán trực tiếp văn bản chương truyện vào đây."
        value={value}
        disabled={disabled}
        onChange={(e) => {
          setIsDocxPlaceholder(false);
          onChange(e.target.value);
        }}
      />

      <p className="text-right text-xs text-muted-foreground font-mono">
        {isDocxPlaceholder
          ? "Số từ sẽ được tính sau khi gửi (nội dung .docx chưa được đọc)"
          : `${wordCount.toLocaleString("vi-VN")} từ`}
      </p>
    </div>
  );
}
