"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Trash2, X } from "lucide-react";

// 3 the duy nhat VieNeu-TTS ho tro chinh thuc (xem README "Emotion cues
// (experimental)" + data/emotion_lexicon.json._note) - hien thi lam goi y
// bam-de-them, khong ep buoc vi nguoi dung van co the tu go the khac de thu.
const SUGGESTED_TAGS = ["[cười]", "[thở dài]", "[hắng giọng]"];

interface Props {
  value: Record<string, string[]>;
  onChange: (next: Record<string, string[]>) => void;
}

export default function EmotionLexiconEditor({ value, onChange }: Props) {
  const [pendingTag, setPendingTag] = useState<Record<string, string>>({});
  const [newLabel, setNewLabel] = useState("");

  const labels = Object.keys(value);

  function addTag(label: string, rawTag: string) {
    const tag = rawTag.trim();
    if (!tag) return;
    const current = value[label] ?? [];
    if (current.includes(tag)) return;
    onChange({ ...value, [label]: [...current, tag] });
    setPendingTag((p) => ({ ...p, [label]: "" }));
  }

  function removeTag(label: string, tag: string) {
    onChange({ ...value, [label]: (value[label] ?? []).filter((t) => t !== tag) });
  }

  function addLabel() {
    const label = newLabel.trim();
    if (!label || label in value) return;
    onChange({ ...value, [label]: [] });
    setNewLabel("");
  }

  function removeLabel(label: string) {
    const next = { ...value };
    delete next[label];
    onChange(next);
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Mỗi nhãn cảm xúc ánh xạ tới danh sách từ/thẻ mà Beta sẽ chọn 1 khi chèn. Sửa danh sách từ
        của 1 nhãn có sẵn có hiệu lực ngay sau khi lưu; <strong>thêm hoặc xoá cả một nhãn cần khởi
        động lại backend</strong> mới có hiệu lực với Alpha/Beta.
      </p>

      {labels.length === 0 && (
        <p className="text-xs italic text-muted-foreground">Chưa có nhãn cảm xúc nào.</p>
      )}

      <div className="space-y-2">
        {labels.map((label) => {
          const tags = value[label] ?? [];
          const suggestions = SUGGESTED_TAGS.filter((t) => !tags.includes(t));
          return (
            <Card key={label} size="sm">
              <CardHeader className="flex-row items-center justify-between gap-2">
                <CardTitle className="font-mono text-sm">{label}</CardTitle>
                <CardAction>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => removeLabel(label)}
                    title="Xoá nhãn (cần khởi động lại backend)"
                    aria-label={`Xoá nhãn ${label}`}
                  >
                    <Trash2 />
                  </Button>
                </CardAction>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  {tags.length === 0 && (
                    <span className="text-xs italic text-muted-foreground">Chưa có từ nào</span>
                  )}
                  {tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="gap-1">
                      <span className="font-mono">{tag}</span>
                      <button
                        type="button"
                        onClick={() => removeTag(label, tag)}
                        aria-label={`Xoá ${tag}`}
                        className="rounded-full hover:text-destructive"
                      >
                        <X className="size-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
                <div className="flex items-center gap-1.5">
                  <Input
                    value={pendingTag[label] ?? ""}
                    onChange={(e) => setPendingTag((p) => ({ ...p, [label]: e.target.value }))}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addTag(label, pendingTag[label] ?? "");
                      }
                    }}
                    placeholder="Thêm từ/thẻ..."
                    className="h-7 text-xs"
                  />
                  <Button
                    size="icon-sm"
                    variant="outline"
                    onClick={() => addTag(label, pendingTag[label] ?? "")}
                    aria-label={`Thêm từ vào nhãn ${label}`}
                  >
                    <Plus />
                  </Button>
                </div>
                {suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {suggestions.map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => addTag(label, tag)}
                        className="rounded-full border border-dashed px-2 py-0.5 font-mono text-[0.7rem] text-muted-foreground hover:bg-muted"
                      >
                        + {tag}
                      </button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="flex items-center gap-1.5 border-t pt-2">
        <Input
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addLabel();
            }
          }}
          placeholder="Tên nhãn mới (vd: gian_du)"
          className="h-7 text-xs"
        />
        <Button size="sm" variant="outline" onClick={addLabel}>
          <Plus /> Thêm nhãn
        </Button>
      </div>
    </div>
  );
}
