import type { NewTermCandidate, SubmitResponse, VoicePresets } from "./types";

// "" (rong) = dung DUONG DAN TUONG DOI, tuc goi ve CUNG origin da tai trang
// - dung cho che do Docker Compose that (Section 12 cua spec): trinh duyet
// chi biet 1 dia chi la nginx (vd. http://localhost hoac domain that), nginx
// moi la thu proxy /api/* toi backend:8000 NOI BO trong mang Docker - cong
// 8000 KHONG duoc publish ra host (xem docker-compose.yml: backend chi co
// "expose", khong co "ports"). Neu bake cung "http://localhost:8000" vao
// bundle luc build (loi THAT xay ra 2026-09-10 - xem git log), trinh duyet
// se co goi THANG toi :8000 va bi ERR_CONNECTION_REFUSED vi khong co gi
// lang nghe o do tu ben ngoai container.
//
// Chi set NEXT_PUBLIC_API_URL (vd. "http://localhost:8000") khi chay che do
// "local dev servers" KHONG qua Docker/nginx (2 tien trinh rieng, port khac
// nhau that su) - xem frontend/.env.local va docs/voxdirector/RUNNING.md.
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface WsStartOptions {
  voiceId: string;
  pauseDurationMs: number;
  qaEnabled: boolean;
  betaEnabled: boolean;
  burnSubtitles: boolean;
}

// Options di kem qua query string cua WebSocket URL - HTTP GET/POST body
// khong ap dung cho handshake WebSocket, va tach 1 endpoint POST rieng de
// "khoi dong" job truoc khi mo WS se can them 1 buoc round-trip + luu state
// phia server giua 2 request khong lien tuc; query params la cach don gian
// nhat de giong/tuy chon nang cao (da chinh sau khi Alpha goi y) den duoc
// dung luc backend bat dau chay Beta/TTS that qua WS.
export function wsUrlFor(jobId: string, opts: WsStartOptions): string {
  // QUAN TRONG: khac voi fetch(), "new WebSocket(url)" KHONG chap nhan URL
  // tuong doi kieu "/api/ws/xyz" - trinh duyet resolve no ve scheme
  // http(s), roi WebSocket constructor nem SyntaxError vi scheme phai la
  // ws/wss. Khi API_BASE_URL rong (che do nginx, cung origin), phai tu
  // dung window.location de dung dung scheme ws/wss + host hien tai.
  const wsBase = API_BASE_URL
    ? API_BASE_URL.replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
  const params = new URLSearchParams({
    voice_id: opts.voiceId,
    pause_duration_ms: String(opts.pauseDurationMs),
    qa_enabled: String(opts.qaEnabled),
    beta_enabled: String(opts.betaEnabled),
    burn_subtitles: String(opts.burnSubtitles),
  });
  return `${wsBase}/api/ws/${jobId}?${params.toString()}`;
}

// 2026-09-12 - anh nen la binary, khong hop voi body JSON cua /api/submit -
// multipart rieng, goi SAU khi co job_id (tu submitText()) nhung TRUOC khi mo
// WebSocket. Xem backend/app/main.py:upload_background_image().
export async function uploadBackgroundImage(jobId: string, file: File): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/api/background-image/${jobId}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Tải ảnh nền thất bại"));
}

export async function fetchVoicePresets(): Promise<VoicePresets> {
  const res = await fetch(`${API_BASE_URL}/api/voices`);
  if (!res.ok) throw new Error(`Không tải được danh sách giọng (${res.status})`);
  return res.json();
}

// BYOK (Section 13 cua spec, chot 2026-09-10): key rieng cua nguoi dung, chi
// luu o TRINH DUYET (localStorage) - khong bao gio gui di dau ngoai backend
// cua chinh app nay luc xu ly that su, khong luu server-side lau dai (backend
// chi giu tam trong bo nho theo job, xem backend/app/main.py). Phu hop pham
// vi "demo/beta vai nguoi dung", KHONG phai co che luu tru bi mat san xuat.
const BYOK_STORAGE_KEY = "voxdirector_byok_gemini_key";

export function getStoredApiKey(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(BYOK_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setStoredApiKey(key: string): void {
  if (typeof window === "undefined") return;
  try {
    if (key.trim()) {
      window.localStorage.setItem(BYOK_STORAGE_KEY, key.trim());
    } else {
      window.localStorage.removeItem(BYOK_STORAGE_KEY);
    }
  } catch {
    // localStorage co the bi chan (che do an danh/private, quyen trinh
    // duyet) - khong lam sap app, chi coi nhu chua luu duoc.
  }
}

async function extractErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // response khong phai JSON - dung fallback ben duoi.
  }
  return `${fallback} (${res.status})`;
}

export async function submitText(
  text: string,
  apiKey?: string,
  alphaEnabled: boolean = true
): Promise<SubmitResponse> {
  const res = await fetch(`${API_BASE_URL}/api/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, api_key: apiKey || null, alpha_enabled: alphaEnabled }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Gửi văn bản thất bại"));
  return res.json();
}

// Step 13 cua build order - Settings screen: 3 file du lieu team-curated,
// tat ca deu "replace-on-upload" (GET doc nguyen file, POST ghi de toan bo)
// - dung 1 cap ham generic thay vi lap lai 6 ham gan giong het nhau.
function settingsEndpoint(key: "emotion-lexicon" | "glossary-seed" | "punctuation-pauses") {
  return `${API_BASE_URL}/api/settings/${key}`;
}

export async function fetchSettingsFile(
  key: "emotion-lexicon" | "glossary-seed" | "punctuation-pauses"
): Promise<Record<string, unknown>> {
  const res = await fetch(settingsEndpoint(key));
  if (!res.ok) throw new Error(`Không tải được ${key} (${res.status})`);
  return res.json();
}

export async function uploadSettingsFile(
  key: "emotion-lexicon" | "glossary-seed" | "punctuation-pauses",
  payload: Record<string, unknown>
): Promise<void> {
  const res = await fetch(settingsEndpoint(key), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Lưu ${key} thất bại (${res.status})`);
}

// Section 5a cua PHASE0_HANDOFF.md (P0) - ghi 1 new_entry_candidate da duoc
// nguoi dung xac nhan ("Duyet") vao glossary that (ChromaDB, phia backend) -
// truoc ban sua nay khong co endpoint nay, nut "Duyet" chi xoa khoi danh
// sach hien thi ma khong ghi gi ca.
export async function approveNewTerm(candidate: NewTermCandidate): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/glossary/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ term: candidate.term, entity_type: candidate.entity_type }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Duyệt thuật ngữ thất bại"));
}

// Step 10 cua build order - "Segment re-render endpoint". Tra ve audio_url
// giu nguyen (backend ghi de cung file final.wav) - caller nen them
// cache-busting query (vd. ?t=Date.now()) khi gan lai vao <audio src> de
// trinh duyet khong dung ban cache cu.
export async function rerenderSegment(jobId: string, segmentId: number): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/rerender`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, segment_id: segmentId }),
  });
  if (!res.ok) throw new Error(`Render lại thất bại (${res.status})`);
}
