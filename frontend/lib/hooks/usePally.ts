/**
 * usePally.ts — Phase 1B 김민주
 * 
 * /api/chat 응답을 받아 PallyCanvas에 넘길 axes를 관리하는 hook.
 * 1A(이찬희)가 메인 화면에서 이 hook만 import해서 쓰면 됨.
 *
 * 사용법:
 *   const { axes, updateFromChatResponse, isLoading, setIsLoading } = usePally();
 *   <PallyCanvas axes={axes} />
 */

import { useState, useRef, useCallback } from 'react';
import { Axes, DEFAULT_AXES, ChatApiResponse } from '@/lib/types/character';

interface UsePallyReturn {
  /** PallyCanvas에 직접 넘길 axes */
  axes: Axes;
  /** /api/chat 응답 받으면 이 함수 호출 — 세션 종료 전까지 표시에는 반영 안 됨 */
  updateFromChatResponse: (res: ChatApiResponse) => void;
  /** 세션 종료 시 호출 → 누적된 axes를 화면에 반영 */
  revealAxes: () => void;
  /** STT 녹음 중 / Gemini 응답 대기 중 여부 */
  isLoading: boolean;
  setIsLoading: (v: boolean) => void;
  /** axes 초기화 */
  resetAxes: () => void;
}

export function usePally(): UsePallyReturn {
  const [axes, setAxes] = useState<Axes>(DEFAULT_AXES);
  const [isLoading, setIsLoading] = useState(false);
  // Accumulates per-turn axes without triggering re-renders
  const pendingAxes = useRef<Axes>(DEFAULT_AXES);

  const updateFromChatResponse = useCallback((res: ChatApiResponse) => {
    pendingAxes.current = res.axes;
  }, []);

  const revealAxes = useCallback(() => {
    setAxes(pendingAxes.current);
    pendingAxes.current = DEFAULT_AXES;
  }, []);

  const resetAxes = useCallback(() => {
    setAxes(DEFAULT_AXES);
    pendingAxes.current = DEFAULT_AXES;
  }, []);

  return { axes, updateFromChatResponse, revealAxes, isLoading, setIsLoading, resetAxes };
}