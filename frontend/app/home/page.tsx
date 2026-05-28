'use client';

import { useCallback, useEffect, useReducer } from 'react';
import { reducer, initialState } from '@/lib/state/conversation';
import { useRecorder } from '@/lib/audio/useRecorder';
import { mockChat } from '@/lib/mocks/chat-mock';
import type { Message } from '@/lib/types/message';
import type { ChatApiResponse } from '@/lib/types/character';
import { usePally } from '@/lib/hooks/usePally';
import PallyCanvas from '@/components/pally/PallyCanvas';
import { EmptyGreeting } from '@/components/chat/EmptyGreeting';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { TalkButton } from '@/components/audio/TalkButton';
import { BottomNav } from '@/components/nav/BottomNav';
import { Toast } from '@/components/ui/Toast';

// Layout coordinates from Figma 427:2216 "Pally talk - 새 채팅" (402×874):
//   empty-title       y=253  (gap 16 from hint)
//   empty-hint        y=293
//   Pally character   y=370  w=h=262 → ends y=632
//   TalkButton idle   y=616  w=h=104 → ends y=720 (overlaps character bottom 16px)
//   GNB               y=753  w=389 h=110
// All absolute-positioned relative to the 402-wide main container so the
// composition matches Figma 1:1 on mobile.

export default function Page() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const { axes, updateFromChatResponse, revealAxes } = usePally();

  // Persist sessionId in localStorage so refresh reuses the same session.
  // SSR-safe: window check, only runs client-side.
  useEffect(() => {
    if (state.sessionId !== null) return;
    const KEY = 'pally:sessionId';
    const stored = window.localStorage.getItem(KEY);
    if (stored) {
      dispatch({ type: 'sessionId/set', id: stored });
      return;
    }
    const id =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `session-${Date.now()}`;
    window.localStorage.setItem(KEY, id);
    dispatch({ type: 'sessionId/set', id });
  }, [state.sessionId]);

  const transcribeAudio = useCallback(async (blob: Blob) => {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
    if (!backendUrl) {
      throw new Error('NEXT_PUBLIC_BACKEND_URL is not configured');
    }

    const formData = new FormData();
    formData.append('audio', blob, 'recording.webm');

    const response = await fetch(`${backendUrl}/api/stt`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`STT failed ${response.status}: ${text}`);
    }

    const data = await response.json();
    return data.transcript as string;
  }, []);

  const handleProcessed = useCallback(
    async (utterance: string) => {
      if (!state.sessionId) return;
      try {
        const res = await mockChat({
          utterance,
          session_id: state.sessionId,
          level: 'B1',
        });
        const userMsg: Message = {
          id: `m-${Date.now()}-u`,
          sessionId: state.sessionId,
          role: 'user',
          transcript: res.transcript,
          createdAt: new Date().toISOString(),
        };
        const pallyMsg: Message = {
          id: `m-${Date.now()}-p`,
          sessionId: state.sessionId,
          role: 'pally',
          transcript: res.reply,
          createdAt: new Date().toISOString(),
        };
        dispatch({ type: 'rec/processed', userMsg, pallyMsg });
        updateFromChatResponse(res as unknown as ChatApiResponse);

        if (res.tts_audio) {
          const bytes = Uint8Array.from(atob(res.tts_audio), (c) => c.charCodeAt(0));
          const url = URL.createObjectURL(new Blob([bytes], { type: 'audio/mpeg' }));
          const audio = new Audio(url);
          const finish = () => {
            URL.revokeObjectURL(url);
            dispatch({ type: 'rec/speakingDone' });
          };
          audio.onended = finish;
          audio.onerror = finish;
          void audio.play().catch(finish);
        } else {
          window.setTimeout(() => dispatch({ type: 'rec/speakingDone' }), 3000);
        }
      } catch {
        dispatch({
          type: 'rec/error',
          reason: 'generic',
          message: '응답을 가져오지 못했어요. 다시 시도해 주세요.',
        });
      }
    },
    [state.sessionId, updateFromChatResponse],
  );

  const recorder = useRecorder({
    onStart: () => dispatch({ type: 'rec/start' }),
    onStop: async (blob) => {
      dispatch({ type: 'rec/stop' });
      if (!state.sessionId) {
        dispatch({
          type: 'rec/error',
          reason: 'generic',
          message: '세션 ID를 생성하는 중입니다. 잠시 후 다시 시도해주세요.',
        });
        return;
      }

      if (!blob) {
        dispatch({
          type: 'rec/error',
          reason: 'generic',
          message: '녹음된 오디오를 찾을 수 없습니다. 다시 시도해주세요.',
        });
        return;
      }

      try {
        const utterance = await transcribeAudio(blob);
        if (!utterance.trim()) {
          throw new Error('음성 인식 결과가 비어있습니다. 다시 시도해주세요.');
        }
        await handleProcessed(utterance);
      } catch (error) {
        const message = error instanceof Error ? error.message : '오디오 처리에 실패했습니다.';
        dispatch({
          type: 'rec/error',
          reason: 'generic',
          message,
        });
      }
    },
    onPermissionDenied: () =>
      dispatch({
        type: 'rec/error',
        reason: 'permission-denied',
        message: '마이크 권한이 필요해요. 브라우저 설정에서 허용해주세요.',
      }),
    onError: (message) =>
      dispatch({ type: 'rec/error', reason: 'generic', message }),
  });

  const handleSessionEnd = useCallback(() => {
    revealAxes(); // Apply accumulated axes to Pally before clearing conversation
    const KEY = 'pally:sessionId';
    const newId =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `session-${Date.now()}`;
    window.localStorage.setItem(KEY, newId);
    dispatch({ type: 'session/end', newId });
  }, [revealAxes]);

  const handlePressStart = useCallback(() => {
    void recorder.start();
  }, [recorder]);

  const handlePressStop = useCallback(() => {
    dispatch({ type: 'rec/stop' }); // Immediately switch to processing UI before onstop fires
    recorder.stop();
  }, [recorder]);

  const isIdle = state.rec.kind === 'idle';
  const isProcessing = state.rec.kind === 'processing';
  const isRecording = state.rec.kind === 'recording';
  const errorVisible = state.rec.kind === 'error';
  // ChatBubble shows whenever there are messages (stays visible through idle/speaking).
  // Disappears only during recording (mic active) or error state.
  // X button clears messages → ChatBubble hides → empty greeting returns.
  const showChatBubble = state.messages.length > 0 && !isRecording && !errorVisible;
  const showEmptyGreeting = isIdle && state.messages.length === 0;
  // Character + TalkButton: hidden only when history is expanded *during* a live conversation.
  // In idle the greeting takes over, so historyOpen residue must not blank the screen.
  const historyCoversScreen = state.historyOpen && !isIdle;
  const showCharacter = !historyCoversScreen;

  // TalkButton y shifts when ChatBubble is above it.
  const talkButtonTop = showChatBubble ? 625 : 616;

  return (
    <main className="relative mx-auto w-full max-w-[402px] min-h-[874px] bg-surface overflow-hidden">
      {/* X button — session end, always visible (Figma 상단 좌측) */}
      <button
        type="button"
        aria-label="세션 종료"
        onClick={handleSessionEnd}
        className="absolute top-4 left-4 z-50 w-8 h-8 flex items-center justify-center"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M4 4l12 12M16 4L4 16" stroke="#1a1a1a" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>

      {/* Top: ChatBubble (covers top region from y=0). Long mode covers character + button. */}
      {showChatBubble && (
        <div className="absolute top-0 inset-x-0 z-10">
          <ChatBubble
            messages={state.messages}
            expanded={state.historyOpen}
            thinking={isProcessing}
            onToggleExpand={() => dispatch({ type: 'history/toggle' })}
          />
        </div>
      )}

      {/* EmptyGreeting at y=253 (Figma empty-title) */}
      {showEmptyGreeting && (
        <div className="absolute top-[253px] inset-x-0 flex justify-center z-10">
          <EmptyGreeting />
        </div>
      )}

      {/* Pally character at y=370 (Figma Group 7) — 1B PallyCanvas with axes */}
      {showCharacter && (
        <div className="absolute top-[370px] left-1/2 -translate-x-1/2 z-0">
          <PallyCanvas axes={axes} size={262} />
        </div>
      )}

      {/* TalkButton: hidden during processing/speaking — user already tapped, no double input */}
      {!historyCoversScreen && state.rec.kind !== 'processing' && state.rec.kind !== 'speaking' && (
        <div
          className="absolute left-1/2 -translate-x-1/2 z-20"
          style={{ top: talkButtonTop }}
        >
          <TalkButton
            rec={state.rec}
            onPressStart={handlePressStart}
            onPressStop={handlePressStop}
          />
        </div>
      )}

      {/* Toast above BottomNav */}
      <div className="absolute bottom-[100px] inset-x-0 px-4 z-40">
        <Toast
          message={state.rec.kind === 'error' ? state.rec.message : ''}
          visible={errorVisible}
          onDismiss={() => dispatch({ type: 'rec/dismissError' })}
        />
      </div>

      {/* GNB fixed at bottom */}
      <BottomNav />
    </main>
  );
}
