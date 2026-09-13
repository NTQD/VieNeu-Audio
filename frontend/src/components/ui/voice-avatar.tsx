import { cn } from "@/lib/utils"

// Thay the cho <Orb> cua ElevenLabs UI (registry goc can @react-three/fiber +
// @react-three/drei + three - toan bo stack WebGL/3D chi de ve 1 avatar nho
// trong danh sach giong) - qua nang cho 1 app noi bo, ngan sach thap
// (VOXDIRECTOR.md: "chi la du an sinh vien, can tiet kiem toi da"). Dung lai
// chinh mo-tip cua logo (dau thanh = mini equalizer) o dang CSS thuan, "talking"
// = 3 vach nhun theo animation khi dang phat am thanh.
export default function VoiceAvatar({
  talking = false,
  className,
}: {
  talking?: boolean
  className?: string
}) {
  return (
    <div
      className={cn(
        "relative flex size-8 shrink-0 items-center justify-center gap-[3px] rounded-full bg-gradient-to-br from-lacquer/25 to-jade/20 ring-1 ring-border",
        className
      )}
      aria-hidden
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={cn(
            "w-[2.5px] rounded-full bg-lacquer",
            talking ? "animate-[voice-bar_0.9s_ease-in-out_infinite]" : "h-2 opacity-60"
          )}
          style={talking ? { animationDelay: `${i * 0.15}s` } : undefined}
        />
      ))}
    </div>
  )
}
