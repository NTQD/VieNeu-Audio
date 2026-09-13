// Bieu tuong VoxDirector AI (2026-09-12, rebrand theo ElevenLabs UI adoption).
// Y tuong: KHONG dung mo-tip "soundwave trong vong tron" chung chung cua moi
// app AI-voice - thay vao do, bien 1 DAU THANH tieng Viet (sac/huyen/hoi/nga/
// nang) thanh 1 mini-equalizer/waveform: 3 vach doc cao thap khac nhau, dat
// o dung VI TRI cua dau thanh (phia tren dinh chu V) - "giong noi CO thanh
// dieu" theo dung nghia den. Rieng cho chinh chu de nay (TTS tieng Viet), khong
// phai icon AI-voice chung chung dung duoc cho bat ky app nao.
export default function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className={className} aria-hidden>
      {/* Than chu V - "Vox" */}
      <path
        d="M7 14 L19 30 L33 14"
        stroke="currentColor"
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* "Dau thanh" = mini equalizer, 3 vach cao thap khac nhau, dat dung
          vi tri 1 dau sac/huyen se nam phia tren nguyen am */}
      <rect x="13.5" y="4" width="3" height="8" rx="1.5" className="fill-lacquer" />
      <rect x="18.5" y="1" width="3" height="13" rx="1.5" className="fill-lacquer" />
      <rect x="23.5" y="6" width="3" height="6.5" rx="1.5" className="fill-lacquer" />
    </svg>
  );
}
