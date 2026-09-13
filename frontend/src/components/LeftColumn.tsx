"use client";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { VoicePicker } from "@/components/ui/voice-picker";
import TextInputArea from "./TextInputArea";
import GenreVoiceSuggestion from "./GenreVoiceSuggestion";
import AgentRail from "./AgentRail";
import AdvancedOptions from "./AdvancedOptions";
import { toPickerVoices } from "@/lib/voice-adapter";
import type { AdvancedOptionsState, SubmitResponse, VoiceOption } from "@/lib/types";

interface Props {
  text: string;
  onTextChange: (t: string) => void;
  alphaResult: SubmitResponse | null;
  voices: VoiceOption[];
  selectedVoiceId: string;
  onVoiceChange: (id: string) => void;
  advanced: AdvancedOptionsState;
  onAdvancedChange: (next: AdvancedOptionsState) => void;
  onStart: () => void;
  isProcessing: boolean;
}

// Cot trai - "Ban thao" (Script). 2026-09-12: giong doc + Agent chuyen thanh
// dieu khien hang dau (luon hien), "San xuat" (bg image/music/pause/subtitle)
// thu gon vi it dung hon - xem design plan trong lich su hoi thoai.
export default function LeftColumn({
  text,
  onTextChange,
  alphaResult,
  voices,
  selectedVoiceId,
  onVoiceChange,
  advanced,
  onAdvancedChange,
  onStart,
  isProcessing,
}: Props) {
  return (
    <div className="space-y-4">
      <TextInputArea value={text} onChange={onTextChange} disabled={isProcessing} />

      {alphaResult && <GenreVoiceSuggestion result={alphaResult} />}

      <div className="space-y-1.5">
        <Label>Giọng đọc</Label>
        <VoicePicker
          voices={toPickerVoices(voices)}
          value={selectedVoiceId}
          onValueChange={onVoiceChange}
          placeholder="Chọn giọng đọc..."
        />
      </div>

      <AgentRail value={advanced} onChange={onAdvancedChange} />

      <AdvancedOptions value={advanced} onChange={onAdvancedChange} />

      <Button
        className="w-full"
        size="lg"
        disabled={!text.trim() || isProcessing}
        onClick={onStart}
      >
        {isProcessing ? "Đang xử lý..." : "Bắt đầu xử lý"}
      </Button>
    </div>
  );
}
