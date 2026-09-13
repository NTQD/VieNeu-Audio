import type { Metadata } from "next";
import { Fraunces, Be_Vietnam_Pro, JetBrains_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

// 2026-09-12 - rebrand (ElevenLabs UI adoption): 3 vai trò chữ riêng biệt,
// không dùng chung 1 font cho mọi thứ như bản Geist mặc định trước đây.
// Fraunces + Be Vietnam Pro đều có subset "vietnamese" đầy đủ dấu - bắt buộc
// vì gần như toàn bộ nội dung UI là tiếng Việt có dấu.
const fraunces = Fraunces({
  variable: "--font-display",
  subsets: ["latin", "vietnamese"],
  weight: ["500", "600"],
});

const beVietnamPro = Be_Vietnam_Pro({
  variable: "--font-body",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600"],
});

const jetBrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "VoxDirector AI",
  description: "Chuyển văn bản truyện tiếng Việt thành audiobook có giọng đọc AI, đa Agent kiểm duyệt chất lượng.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="vi"
      suppressHydrationWarning
      className={`${fraunces.variable} ${beVietnamPro.variable} ${jetBrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-body">
        {/* defaultTheme="system" - nguoi dung yeu cau "theo tuy chon sang/toi
            cua thiet bi" - dark la huong tham my CHINH duoc dau tu ky (xem
            globals.css) nhung KHONG ep cung, he thong/nguoi dung tu quyet
            dinh qua ThemeToggle. */}
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
