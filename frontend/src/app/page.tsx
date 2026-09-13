"use client";

import { useEffect, useRef, useState } from "react";
import LeftColumn from "@/components/LeftColumn";
import WorkArea, { type WorkAreaState } from "@/components/WorkArea";
import NewTermConfirmationPanel from "@/components/NewTermConfirmationPanel";
import SettingsPanel from "@/components/SettingsPanel";
import Logo from "@/components/Logo";
import ThemeToggle from "@/components/ThemeToggle";
import { fetchVoicePresets, getStoredApiKey, submitText, uploadBackgroundImage, wsUrlFor } from "@/lib/api";
import type {
  AdvancedOptionsState,
  NewTermCandidate,
  ProgressMessage,
  ResultMessage,
  SubmitResponse,
  VoiceOption,
  WsMessage,
} from "@/lib/types";

export default function Home() {
  const [text, setText] = useState("");
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [alphaResult, setAlphaResult] = useState<SubmitResponse | null>(null);
  const [selectedVoiceId, setSelectedVoiceId] = useState("");
  const [advanced, setAdvanced] = useState<AdvancedOptionsState>({
    backgroundImage: null,
    backgroundMusic: null,
    pauseDurationMs: 500,
    burnSubtitles: true,
    qaEnabled: false,
    alphaEnabled: true,
    betaEnabled: true,
  });
  const [workArea, setWorkArea] = useState<WorkAreaState>({ kind: "empty" });
  const [newTerms, setNewTerms] = useState<NewTermCandidate[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    fetchVoicePresets()
      .then((presets) => setVoices(presets.voices))
      .catch((err) => console.error("Không tải được danh sách giọng:", err));
  }, []);

  const isProcessing = workArea.kind === "progress";

  async function handleStart() {
    setWorkArea({ kind: "progress", latest: null });
    setNewTerms([]);
    setSubmitError(null);

    let submitResult: SubmitResponse;
    try {
      submitResult = await submitText(text, getStoredApiKey(), advanced.alphaEnabled);
    } catch (err) {
      console.error(err);
      setSubmitError(err instanceof Error ? err.message : "Gửi văn bản thất bại");
      setWorkArea({ kind: "empty" });
      return;
    }
    setAlphaResult(submitResult);
    const voiceId = selectedVoiceId || submitResult.suggested_voice_id;
    setSelectedVoiceId(voiceId);

    // Anh nen (neu co) phai upload xong TRUOC khi mo WS - ws_progress() chi
    // render video khi job["background_image_path"] da co san luc no chay
    // toi buoc ghep audio (xem backend/app/main.py).
    if (advanced.backgroundImage) {
      try {
        await uploadBackgroundImage(submitResult.job_id, advanced.backgroundImage);
      } catch (err) {
        console.error(err);
        setSubmitError(err instanceof Error ? err.message : "Tải ảnh nền thất bại");
        setWorkArea({ kind: "empty" });
        return;
      }
    }

    const ws = new WebSocket(
      wsUrlFor(submitResult.job_id, {
        voiceId,
        pauseDurationMs: advanced.pauseDurationMs,
        qaEnabled: advanced.qaEnabled,
        betaEnabled: advanced.betaEnabled,
        burnSubtitles: advanced.burnSubtitles,
      })
    );
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg: WsMessage = JSON.parse(event.data);
      if (msg.type === "progress") {
        setWorkArea({ kind: "progress", latest: msg as ProgressMessage });
      } else if (msg.type === "result") {
        const result = msg as ResultMessage;
        setWorkArea({ kind: "result", result, qaEnabled: advanced.qaEnabled, jobId: submitResult.job_id });
        setNewTerms(result.new_term_candidates);
      } else if (msg.type === "error") {
        setSubmitError(msg.message || "Xử lý thất bại");
        setWorkArea({ kind: "empty" });
      }
    };
    ws.onerror = () => {
      setSubmitError("Mất kết nối WebSocket tới backend.");
      setWorkArea({ kind: "empty" });
    };
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <Logo />
          <div className="flex items-center gap-1">
            <SettingsPanel />
            <ThemeToggle />
          </div>
        </div>

        {submitError && (
          <div className="mb-6 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {submitError}
          </div>
        )}

        {/* Section 8.1.1: 2 cot tren desktop (md: tro len), xep chong 1 cot
            tren mobile (duoi md) - breakpoint chuan cua Tailwind (~768px). */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <LeftColumn
            text={text}
            onTextChange={setText}
            alphaResult={alphaResult}
            voices={voices}
            selectedVoiceId={selectedVoiceId}
            onVoiceChange={setSelectedVoiceId}
            advanced={advanced}
            onAdvancedChange={setAdvanced}
            onStart={handleStart}
            isProcessing={isProcessing}
          />
          <WorkArea state={workArea} />
        </div>
      </div>

      <NewTermConfirmationPanel
        candidates={newTerms}
        onDismiss={() => setNewTerms([])}
        onApprove={(term) => setNewTerms((prev) => prev.filter((c) => c.term !== term))}
      />
    </main>
  );
}
