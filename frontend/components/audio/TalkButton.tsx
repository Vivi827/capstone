"use client";

import type { RecState } from "@/lib/state/conversation";
import { cn } from "@/lib/utils";

export interface TalkButtonProps {
  rec: RecState;
  disabled?: boolean;
  onPressStart: () => void;
  onPressStop: () => void;
}

const ARIA: Record<RecState["kind"], string> = {
  idle: "녹음 시작",
  recording: "녹음 정지",
  processing: "처리 중",
  speaking: "Pally가 응답 중",
  error: "녹음 시작",
};

export function TalkButton({ rec, disabled = false, onPressStart, onPressStop }: TalkButtonProps) {
  const isRecording = rec.kind === "recording";
  const isInteractive = !disabled && (rec.kind === "idle" || rec.kind === "error" || isRecording);
  const src = isRecording ? "/pally/talkbtn-thinking.svg" : "/pally/talkbtn-idle.svg";

  const handleClick = () => {
    if (!isInteractive) return;
    if (isRecording) {
      onPressStop();
      return;
    }
    onPressStart();
  };

  return (
    <button
      aria-disabled={!isInteractive}
      aria-label={ARIA[rec.kind]}
      className={cn(
        "block touch-manipulation border-0 bg-transparent p-0 transition-transform duration-150 active:scale-95",
        "disabled:cursor-default disabled:opacity-50",
      )}
      disabled={!isInteractive}
      onClick={handleClick}
      style={{ width: 104, height: 104 }}
      type="button"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img alt="" aria-hidden className="pointer-events-none block h-[105.05px] w-full select-none" height={105.05} src={src} width={104} />
    </button>
  );
}
