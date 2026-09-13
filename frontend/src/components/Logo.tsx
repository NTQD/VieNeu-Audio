import LogoMark from "./LogoMark";

export default function Logo({ className }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2.5 ${className ?? ""}`}>
      <LogoMark className="h-8 w-8 text-foreground shrink-0" />
      <span className="font-display text-xl font-semibold tracking-tight leading-none">
        VoxDirector
      </span>
    </div>
  );
}
