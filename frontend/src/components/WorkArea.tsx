"use client";

import ProgressStages from "./ProgressStages";
import ResultView from "./ResultView";
import type { ProgressMessage, ResultMessage } from "@/lib/types";

export type WorkAreaState =
  | { kind: "empty" }
  | { kind: "progress"; latest: ProgressMessage | null }
  | { kind: "result"; result: ResultMessage; qaEnabled: boolean; jobId: string };

interface Props {
  state: WorkAreaState;
}

// Cot phai - Section 8.1.1: rong luc dau, roi hien progress (WebSocket-
// driven), roi hien ket qua - CUNG 1 cot, khong phai man hinh rieng, LUON
// hien thi song song voi cot trai (khong bao gio thay the no).
export default function WorkArea({ state }: Props) {
  return (
    <div className="rounded-lg border p-6 min-h-[400px] flex flex-col">
      {state.kind === "empty" && (
        <div className="flex-1 flex items-center justify-center text-center">
          <p className="text-sm text-muted-foreground max-w-xs">
            Kết quả xử lý sẽ hiện ở đây sau khi bạn bấm &ldquo;Bắt đầu xử lý&rdquo; ở cột bên trái.
          </p>
        </div>
      )}
      {state.kind === "progress" && (
        <div className="flex-1 flex items-center justify-center">
          <div className="w-full max-w-sm">
            <ProgressStages latest={state.latest} />
          </div>
        </div>
      )}
      {state.kind === "result" && (
        <ResultView result={state.result} qaEnabled={state.qaEnabled} jobId={state.jobId} />
      )}
    </div>
  );
}
