'use client';

import { cn } from '@/lib/utils';
import type { RecState } from '@/lib/state/conversation';

export interface TalkButtonProps {
  rec: RecState;
  disabled?: boolean;
  onPressStart: () => void;
  onPressStop: () => void;
}

// Figma TalkButton ComponentSet (441:30) — two variants exported as PNG:
//   - state=idle    (node 441:18)   → orange disc + white mic + drop shadow
//   - state=thinking (node 427:2622) → red disc + white square stop + drop shadow
// PNGs include the drop shadow baked in (transparent background).

const ARIA: Record<RecState['kind'], string> = {
  idle: '녹음 시작',
  recording: '녹음 정지',
  processing: '처리 중',
  speaking: 'Pally가 응답 중',
  error: '녹음 시작',
};

export function TalkButton({ rec, disabled = false, onPressStart, onPressStop }: TalkButtonProps) {
  const isThinkingVariant = rec.kind === 'recording' || rec.kind === 'processing';
  const isInteractive =
    !disabled &&
    (rec.kind === 'idle' || rec.kind === 'error' || rec.kind === 'recording');

  const handleClick = () => {
    if (!isInteractive) return;
    if (rec.kind === 'recording') {
      onPressStop();
    } else {
      onPressStart();
    }
  };

  // Thinking PNG is 104×109 (drop shadow extends 5px below). idle is 104×104.
  const src = isThinkingVariant ? '/pally/talkbtn-thinking.png' : '/pally/talkbtn-idle.png';
  const height = isThinkingVariant ? 109 : 104;

  return (
    <button
      type="button"
      aria-label={ARIA[rec.kind]}
      aria-disabled={!isInteractive}
      disabled={!isInteractive}
      onClick={handleClick}
      className={cn(
        'block bg-transparent border-0 p-0',
        'transition-transform duration-150 active:scale-95',
        'disabled:cursor-default',
        'touch-manipulation', // Eliminate 300ms tap delay on mobile
      )}
      style={{ width: 104, height }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt=""
        width={104}
        height={height}
        className="block w-full h-full select-none pointer-events-none"
        aria-hidden
      />
    </button>
  );
}
