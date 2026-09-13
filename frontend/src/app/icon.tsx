import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

// Favicon tao bang code (Next.js icon convention) - dung LAI y tuong logo
// chinh (LogoMark.tsx: dau thanh tieng Viet -> mini equalizer tren dinh chu
// V) - khong the import component React thuong o day (Satori/ImageResponse
// can markup rieng), nen ve lai bang SVG thuan.
export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#28221c",
          borderRadius: 6,
        }}
      >
        <svg width="24" height="24" viewBox="0 0 40 40" fill="none">
          <path d="M7 14 L19 30 L33 14" stroke="#f2ece0" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" />
          <rect x="13.5" y="4" width="3.4" height="8" rx="1.7" fill="#c1443a" />
          <rect x="18.3" y="1" width="3.4" height="13" rx="1.7" fill="#c1443a" />
          <rect x="23.1" y="6" width="3.4" height="6.5" rx="1.7" fill="#c1443a" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
