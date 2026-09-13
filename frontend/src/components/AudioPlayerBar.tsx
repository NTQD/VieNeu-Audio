"use client";

import { useEffect } from "react";
import { RotateCcw, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  AudioPlayerButton,
  AudioPlayerDuration,
  AudioPlayerProvider,
  AudioPlayerSpeed,
  AudioPlayerTime,
  useAudioPlayer,
  useAudioPlayerTime,
} from "@/components/ui/audio-player";

interface Props {
  src: string;
  cacheBust: number;
}

const SKIP_SECONDS = 5;

// 2026-09-12 (phan hoi nguoi dung: "waveform section really bad... leave it
// as normal, remove the waveform display") - bo hoan toan AudioScrubber
// (canvas ve waveform) sau khi xac dinh no CHINH LA nguyen nhan loi "bam nut
// settings lai nhay ve cuoi file": vung click-de-tua cua no phu het chieu
// rong container, de bi lan voi nut gear canh ben khi layout thu hep - dung
// lai Slider (Base UI, da dung o AdvancedOptions, khong co xung dot vung
// click) cho thanh tua, gon hon nhieu so voi khoi waveform cu.
export default function AudioPlayerBar({ src, cacheBust }: Props) {
  return (
    <AudioPlayerProvider>
      <AudioPlayerBarInner src={src} cacheBust={cacheBust} />
    </AudioPlayerProvider>
  );
}

function AudioPlayerBarInner({ src, cacheBust }: Props) {
  const player = useAudioPlayer();
  const currentTime = useAudioPlayerTime();
  const duration = player.duration ?? 0;

  useEffect(() => {
    player.setActiveItem({ id: cacheBust, src });
  }, [src, cacheBust]); // eslint-disable-line react-hooks/exhaustive-deps

  function skip(deltaSeconds: number) {
    player.seek(Math.min(Math.max(currentTime + deltaSeconds, 0), duration || 0));
  }

  return (
    <div className="rounded-lg border bg-card px-3 py-2 flex items-center gap-2">
      <Button
        size="icon"
        variant="ghost"
        className="shrink-0"
        aria-label={`Tua lùi ${SKIP_SECONDS} giây`}
        onClick={() => skip(-SKIP_SECONDS)}
      >
        <RotateCcw className="size-4" />
      </Button>
      <AudioPlayerButton size="icon" variant="ghost" className="rounded-full shrink-0" />
      <Button
        size="icon"
        variant="ghost"
        className="shrink-0"
        aria-label={`Tua tới ${SKIP_SECONDS} giây`}
        onClick={() => skip(SKIP_SECONDS)}
      >
        <RotateCw className="size-4" />
      </Button>

      <AudioPlayerTime className="w-10 text-right" />
      <Slider
        value={[Math.min(currentTime, duration || 0)]}
        max={duration || 0}
        step={0.1}
        className="flex-1"
        onValueChange={(v) => player.seek(Array.isArray(v) ? v[0] : v)}
      />
      <AudioPlayerDuration className="w-10" />

      <AudioPlayerSpeed variant="ghost" size="icon" className="shrink-0" />
    </div>
  );
}
