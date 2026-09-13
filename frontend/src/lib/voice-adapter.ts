import type { Voice } from "@/components/ui/voice-picker";
import type { VoiceOption } from "./types";
import { API_BASE_URL } from "./api";

// Chuyen doi VoiceOption (schema tra ve tu /api/voices, xem
// data/voice_presets.json) sang Voice (kieu VoicePicker cua ElevenLabs UI
// mong doi) - chi la mapping hien thi, khong lien quan API/SDK cua ElevenLabs.
const REGION_LABELS: Record<string, string> = {
  bac: "Bắc",
  trung: "Trung",
  nam: "Nam",
};

const STYLE_LABELS: Record<string, string> = {
  doc_truyen: "đọc truyện",
  ke_chuyen: "kể chuyện",
  tu_nhien: "tự nhiên",
  tin_tuc: "tin tức",
};

// Ky hieu (KHONG dung chu "Nam" cho gioi tinh) - "Nam" tieng Viet vua co
// nghia "mien Nam" (vung mien) vua co nghia "nam gioi" (gioi tinh), dat canh
// nhau trong 1 dong ("Nam • Nam") gay hieu nham that su (xac nhan khi xem
// lai UI 2026-09-12) - dung icon thay chu de tranh dong am hoan toan.
const GENDER_ICONS: Record<string, string> = {
  male: "♂",
  female: "♀",
};

export function toPickerVoices(voices: VoiceOption[]): Voice[] {
  return voices.map((v) => ({
    voiceId: v.id,
    name: v.display_name.split(" (")[0] || v.display_name,
    // 23 file .wav tinh, tao san 1 lan qua scripts/generate_voice_previews.py
    // (xem backend/app/main.py:get_voice_preview) - VieNeu khong co API
    // preview san nhu ElevenLabs nen phai tu tong hop truoc, khong phai lay
    // truc tiep tu 1 dich vu nao.
    previewUrl: `${API_BASE_URL}/api/voice-preview/${encodeURIComponent(v.id)}`,
    labels: {
      accent: v.region ? `Giọng ${REGION_LABELS[v.region] ?? v.region}` : undefined,
      gender: v.gender ? GENDER_ICONS[v.gender] ?? v.gender : undefined,
      description: v.style ? STYLE_LABELS[v.style] ?? v.style : undefined,
    },
  }));
}
