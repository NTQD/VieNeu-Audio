"use client";

import type { ReactNode } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "cn";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
}

// 2026-09-14 - Dialog du lieu DUNG CHUNG cho ca 3 khu vuc Cai dat du lieu
// (Tu dien cam xuc / Glossary / Bang ngat nghi) - thay the cho viec moi khu
// vuc tu mo rong NGAY BEN TRONG dialog "Cai dat du lieu" nho (van de nguoi
// dung bao cao: ca 3 hien thi CHUNG 1 popup lam no rat dai/chat).
//
// FULLY CONTROLLED (open/onOpenChange tu component cha, KHONG con
// DialogTrigger/state noi bo o day) - XAC NHAN CO THAT qua kiem tra truc
// tiep DOM (2026-09-14): ban dau component nay render DUOI DANG con long
// BEN TRONG <DialogContent> cua dialog "Cai dat du lieu", voi state open
// rieng cua no. Dieu do gay loi that: khi dialog cha dong VA Base UI thao
// bo Popup cua no khoi DOM sau khi animation-out ket thuc, TOAN BO cay JSX
// con cua no (bao gom component nay) bi go theo CUNG LUC - React Portal
// van gan lien voi cay SO HUU (khong phai vi tri DOM thuc te hien thi), nen
// dialog con nay CUNG bi unmount ngay ca khi state open cua CHINH NO dang
// la true. Fix: component nay khong con tu quan ly state/trigger nua - cha
// (SettingsPanel.tsx) render no NHU MOT ANH EM (sibling) CUA dialog "Cai dat
// du lieu", khong long ben trong, va tu quan ly ca 2 state open doc lap.
//
// Kich thuoc theo dung yeu cau nguoi dung, quy ve 1 luat CSS duy nhat thay
// vi 2 luat rieng hay MAU THUAN NHAU tren man hinh nho (vd. 2x chieu rong
// dialog Cai dat du lieu ~672px = ~1344px NHUNG 80% cua 1 laptop 1280px chi
// ~1024px - la 2 gioi han khong the cung dung tren man hinh <~1680px neu ap
// dung nhu 2 luat doc lap):
//   width:  min(80vw, 84rem)   -- 84rem = 2 x 42rem (max-w-2xl cua dialog Cai
//                                  dat du lieu) - "muc tieu" 2x, nhung KHONG
//                                  BAO GIO vuot tran 80% khung nhin.
//   height: min(80vh, 48rem), toi thieu 60vh de khong qua thap voi danh sach
//           ngan (vd. Bang ngat nghi chi ~7 dong).
// Duoi breakpoint sm (~640px, "dien thoai") - CHUYEN HAN sang sheet TOAN MAN
// HINH (khong con la 1 hop noi giua man hinh nua) - day la mau UX chuan cho
// "mo 1 khu vuc sua du lieu lon hon" tren dien thoai (Gmail/Notion/Linear...
// deu lam vay), khong phai 1 modal nho hon dat giua man hinh.
export default function DataViewerDialog({ open, onOpenChange, title, description, children }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          // Dien thoai (mac dinh) - sheet toan man hinh, khong con la hop
          // noi giua/bo goc tron/backdrop-margin nhu dialog nho.
          "inset-0 top-0 left-0 h-[100dvh] w-screen max-w-none translate-x-0 translate-y-0 flex-col rounded-none p-0",
          // sm+ (tablet/desktop) - hop noi giua, kich thuoc theo cong thuc o
          // tren, cuon rieng phan noi dung (header dung yen).
          "sm:inset-auto sm:top-1/2 sm:left-1/2 sm:h-auto sm:max-h-[min(80vh,48rem)] sm:min-h-[60vh] sm:w-[min(80vw,84rem)] sm:max-w-none sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-xl sm:p-4",
          "flex overflow-hidden"
        )}
      >
        <DialogHeader className="shrink-0 p-4 pb-0 sm:p-0">
          <DialogTitle>{title}</DialogTitle>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-0 sm:pt-3">{children}</div>
      </DialogContent>
    </Dialog>
  );
}
