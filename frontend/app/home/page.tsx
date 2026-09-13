"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { TalkButton } from "@/components/audio/TalkButton";
import { ChatBubble } from "@/components/chat/ChatBubble";
import { ConfirmDialog } from "@/components/dialogs/ConfirmDialog";
import { MobileShell } from "@/components/layout/MobileShell";
import { BottomNav } from "@/components/nav/BottomNav";
import PallyCanvas from "@/components/pally/PallyCanvas";
import { PageLoader } from "@/components/ui/PageLoader";
import { Toast } from "@/components/ui/Toast";
import { pallyApi, PallyApiError } from "@/lib/api";
import type { Subscription, UsageResponse } from "@/lib/api";
import { conversationTurnsToMessages } from "@/lib/api/conversation-messages";
import {
  invalidateConversationData,
  invalidateUsage,
  loadConversationPage,
  loadLatestCompletedConversation,
  loadSubscription,
  loadUsage,
  schedulePrimaryRoutePrefetch,
} from "@/lib/api/route-data";
import { blobToMonoWav } from "@/lib/audio/blobToWav";
import { useRecorder } from "@/lib/audio/useRecorder";
import { usePally } from "@/lib/hooks/usePally";
import { initialState, reducer } from "@/lib/state/conversation";
import type { Message } from "@/lib/types/message";
import { supabase } from "@/lib/supabase/client";
import { UsageSummary } from "@/components/usage/UsageSummary";

const CONVERSATION_KEY = "pally:conversationId";

export default function HomePage() {
  const router = useRouter();
  const [state, dispatch] = useReducer(reducer, initialState);
  const { axes, restoreAxes, revealAxes, updateFromChatResponse } = usePally();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const speakingTimerRef = useRef<number | null>(null);
  const pendingTurnRef = useRef<Promise<void> | null>(null);
  const closingRef = useRef(false);
  const conversationIdRef = useRef<string | null>(null);
  const userIdRef = useRef<string | null>(null);
  const [limitDialogOpen, setLimitDialogOpen] = useState(false);
  const [quotaExhausted, setQuotaExhausted] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [isRestoring, setIsRestoring] = useState(true);
  const [hasRestoredPally, setHasRestoredPally] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [pendingUserTranscript, setPendingUserTranscript] = useState<string | null>(null);
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);

  useEffect(() => {
    let active = true;
    let cancelPrefetch: (() => void) | null = null;

    const restoreConversation = async () => {
      const auth = await supabase.auth.getSession();
      if (auth.error) throw auth.error;
      if (!auth.data.session) {
        router.replace("/");
        return;
      }

      const userId = auth.data.session.user.id;
      userIdRef.current = userId;
      const requestedId = new URLSearchParams(window.location.search).get("conversation_id");
      const storedId = window.localStorage.getItem(CONVERSATION_KEY);
      const conversationId = requestedId ?? storedId;

      const usagePromise = loadUsage(userId);
      const completedPromise = loadLatestCompletedConversation(userId);
      const detailPromise = conversationId
        ? loadConversationPage(userId, conversationId)
        : Promise.resolve(null);

      void loadSubscription(userId)
        .then((response) => {
          if (active) setSubscription(response.subscription);
        })
        .catch((error: unknown) => console.error("Subscription status failed", error));

      void pallyApi.recordActivityEvent({
        event_id: crypto.randomUUID(),
        event_type: "app_session_started",
        occurred_at: new Date().toISOString(),
      }).catch((error: unknown) => console.error("Activity event failed", error));

      const [usage, completed, detail] = await Promise.all([
        usagePromise,
        completedPromise,
        detailPromise,
      ]);
      if (!active) return;

      if (active) {
        setUsage(usage);
        const exhausted = usage.remaining_turns === 0;
        setQuotaExhausted(exhausted);
        if (exhausted) setLimitDialogOpen(true);
      }

      const revealedAxes = completed.items[0]?.current_axes;
      if (active && revealedAxes) restoreAxes(revealedAxes);
      setHasRestoredPally(true);

      cancelPrefetch = schedulePrimaryRoutePrefetch(userId);
      if (!conversationId || !detail) return;

      if (detail.conversation.status !== "active") {
        window.localStorage.removeItem(CONVERSATION_KEY);
        return;
      }

      const messages = conversationTurnsToMessages(conversationId, detail.turns);
      if (!active) return;
      conversationIdRef.current = conversationId;
      window.localStorage.setItem(CONVERSATION_KEY, conversationId);
      dispatch({ type: "session/load", id: conversationId, messages });
    };

    void restoreConversation()
      .catch((caught: unknown) => {
        if (caught instanceof PallyApiError && (caught.code === "not_found" || caught.code === "unauthorized")) {
          window.localStorage.removeItem(CONVERSATION_KEY);
          if (caught.code === "unauthorized") router.replace("/");
          return;
        }
        if (active) {
          dispatch({ type: "rec/error", reason: "generic", message: caught instanceof Error ? caught.message : "대화를 불러오지 못했어요." });
        }
      })
      .finally(() => {
        if (active) setIsRestoring(false);
      });
    return () => {
      active = false;
      cancelPrefetch?.();
    };
  }, [restoreAxes, router, updateFromChatResponse]);

  const ensureConversation = useCallback(async () => {
    if (conversationIdRef.current) return conversationIdRef.current;
    const response = await pallyApi.createConversation(crypto.randomUUID());
    const conversationId = response.conversation.id;
    conversationIdRef.current = conversationId;
    window.localStorage.setItem(CONVERSATION_KEY, conversationId);
    if (!closingRef.current) dispatch({ type: "sessionId/set", id: conversationId });
    return conversationId;
  }, []);

  const stopPlayback = useCallback(() => {
    if (speakingTimerRef.current !== null) {
      window.clearTimeout(speakingTimerRef.current);
      speakingTimerRef.current = null;
    }

    const source = audioSourceRef.current;
    audioSourceRef.current = null;
    if (source) {
      source.onended = null;
      try {
        source.stop();
      } catch (error) {
        console.warn("TTS source stop failed.", error);
      }
      source.disconnect();
    }

    const audio = audioRef.current;
    audioRef.current = null;
    if (audio) {
      audio.onended = null;
      audio.onerror = null;
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    }

    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
  }, []);

  const playTts = useCallback(async (encodedAudio: string) => {
    stopPlayback();
    if (closingRef.current) return;

    const base64 = encodedAudio.startsWith("data:") ? encodedAudio.slice(encodedAudio.indexOf(",") + 1) : encodedAudio;
    const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
    let played = false;
    const audioContext = audioContextRef.current;

    if (audioContext && audioContext.state !== "closed") {
      try {
        if (audioContext.state === "suspended") await audioContext.resume();
        const buffer = await audioContext.decodeAudioData(bytes.buffer.slice(0));
        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        if (closingRef.current) {
          source.disconnect();
          return;
        }
        audioSourceRef.current = source;
        source.onended = () => {
          if (audioSourceRef.current !== source) return;
          audioSourceRef.current = null;
          source.disconnect();
          if (!closingRef.current) dispatch({ type: "rec/speakingDone" });
        };
        source.start();
        played = true;
      } catch (error) {
        if (!closingRef.current) {
          console.warn("AudioContext playback failed; using HTMLAudioElement.", error);
        }
      }
    }

    if (played || closingRef.current) return;
    const url = URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" }));
    const audio = new Audio(url);
    audioUrlRef.current = url;
    audioRef.current = audio;
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      const wasCurrent = audioRef.current === audio;
      if (wasCurrent) audioRef.current = null;
      if (audioUrlRef.current === url) audioUrlRef.current = null;
      URL.revokeObjectURL(url);
      if (wasCurrent && !closingRef.current) dispatch({ type: "rec/speakingDone" });
    };
    audio.onended = done;
    audio.onerror = done;
    void audio.play().catch((error) => {
      if (!closingRef.current) console.warn("TTS playback failed.", error);
      done();
    });
  }, [stopPlayback]);

  const handleProcessed = useCallback(
    async (blob: Blob) => {
      try {
        const conversationId = await ensureConversation();
        const response = await pallyApi.createTurn(conversationId, {
          audio: blob,
          client_started_at: new Date().toISOString(),
          idempotency_key: crypto.randomUUID(),
        });
        if (closingRef.current) return;

        const now = Date.now();
        const userMessage: Message = {
          id: `m-${now}-u`,
          sessionId: conversationId,
          role: "user",
          transcript: response.user.transcript,
          createdAt: response.created_at ?? new Date().toISOString(),
        };
        const pallyMessage: Message = {
          id: `m-${now}-p`,
          sessionId: conversationId,
          role: "pally",
          transcript: response.pally.text,
          createdAt: response.created_at ?? new Date().toISOString(),
        };
        setPendingUserTranscript(null);
        dispatch({ type: "rec/processed", userMsg: userMessage, pallyMsg: pallyMessage });
        updateFromChatResponse({ axes: response.axes });
        const userId = userIdRef.current;
        if (userId) {
          invalidateUsage(userId);
          invalidateConversationData(userId, conversationId);
        }
        const quota = response.quota;
        if (quota?.exhausted) {
          setQuotaExhausted(true);
          setLimitDialogOpen(true);
        }
        if (quota) {
          setUsage((current) => ({
            plan: "free",
            date: current?.date ?? new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date()),
            timezone: "Asia/Seoul",
            used_turns: quota.used_turns ?? quota.daily_limit - quota.remaining_turns,
            remaining_turns: quota.remaining_turns,
            daily_limit: quota.daily_limit,
            reset_at: quota.resets_at,
          }));
        }
        const notices = response.warnings.map((item) => item.message);
        if (response.replayed) notices.push("네트워크 재시도로 저장된 응답을 다시 불러왔어요.");
        setWarning(notices.length > 0 ? notices.join(" ") : null);

        if (response.pally.audio) {
          await playTts(response.pally.audio);
        } else {
          stopPlayback();
          speakingTimerRef.current = window.setTimeout(() => {
            speakingTimerRef.current = null;
            if (!closingRef.current) dispatch({ type: "rec/speakingDone" });
          }, 3000);
        }
      } catch (error) {
        console.error("Conversation request failed.", error);
        if (closingRef.current) return;
        setPendingUserTranscript(null);
        if (error instanceof PallyApiError && error.code === "quota_exceeded") {
          setQuotaExhausted(true);
          setLimitDialogOpen(true);
        }
        dispatch({
          type: "rec/error",
          reason: "generic",
          message: error instanceof Error ? error.message : "응답을 가져오지 못했어요. 다시 시도해 주세요.",
        });
      }
    },
    [ensureConversation, playTts, stopPlayback, updateFromChatResponse],
  );

  const recorder = useRecorder({
    onStart: () => {
      if (!closingRef.current) {
        setPendingUserTranscript(null);
        dispatch({ type: "rec/start" });
      }
    },
    onStop: (blob, transcript) => {
      if (closingRef.current) return;
      const normalizedTranscript = transcript?.trim();
      setPendingUserTranscript(normalizedTranscript ? normalizedTranscript : null);
      dispatch({ type: "rec/stop" });

      const pendingTurn = (async () => {
        try {
          if (!blob) throw new Error("녹음된 오디오를 찾을 수 없어요. 다시 시도해 주세요.");
          const wavBlob = await blobToMonoWav(blob);
          await handleProcessed(wavBlob);
        } catch (error) {
          console.error("Audio processing failed.", error);
          if (closingRef.current) return;
          setPendingUserTranscript(null);
          dispatch({
            type: "rec/error",
            reason: "generic",
            message: error instanceof Error ? error.message : "오디오 처리에 실패했어요.",
          });
        }
      })();
      pendingTurnRef.current = pendingTurn;
      void pendingTurn.then(() => {
        if (pendingTurnRef.current === pendingTurn) pendingTurnRef.current = null;
      });
    },
    onPermissionDenied: () => {
      if (!closingRef.current) {
        setPendingUserTranscript(null);
        dispatch({ type: "rec/error", reason: "permission-denied", message: "마이크 권한이 필요해요. 브라우저 설정에서 허용해 주세요." });
      }
    },
    onError: (message) => {
      if (!closingRef.current) {
        setPendingUserTranscript(null);
        dispatch({ type: "rec/error", reason: "generic", message });
      }
    },
  });

  const handleSessionEnd = useCallback(async () => {
    if (closingRef.current) return;
    closingRef.current = true;
    setIsClosing(true);
    setWarning(null);
    recorder.cancel();
    stopPlayback();

    const pendingTurn = pendingTurnRef.current;
    if (pendingTurn) {
      await pendingTurn;
      if (pendingTurnRef.current === pendingTurn) pendingTurnRef.current = null;
    }
    stopPlayback();

    try {
      const conversationId = conversationIdRef.current;
      if (conversationId) await pallyApi.completeConversation(conversationId);
      const userId = userIdRef.current;
      if (userId) invalidateConversationData(userId, conversationId ?? undefined);
      revealAxes();
      setPendingUserTranscript(null);
      conversationIdRef.current = null;
      window.localStorage.removeItem(CONVERSATION_KEY);
      dispatch({ type: "session/end" });
    } catch (caught) {
      dispatch({
        type: "rec/error",
        reason: "generic",
        message: caught instanceof Error ? caught.message : "대화를 종료하지 못했어요.",
      });
    } finally {
      closingRef.current = false;
      setIsClosing(false);
    }
  }, [recorder, revealAxes, stopPlayback]);

  const handlePressStart = useCallback(() => {
    if (closingRef.current || quotaExhausted || isRestoring || !hasRestoredPally) return;
    void recorder.start();
  }, [hasRestoredPally, isRestoring, quotaExhausted, recorder]);

  const handlePressStop = useCallback(() => {
    if (closingRef.current) return;
    dispatch({ type: "rec/stop" });
    try {
      if (!audioContextRef.current) {
        const AudioContextConstructor = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        audioContextRef.current = new AudioContextConstructor();
      }
      if (audioContextRef.current.state === "suspended") void audioContextRef.current.resume();
    } catch (error) {
      console.warn("AudioContext is unavailable.", error);
    }
    recorder.stop();
  }, [recorder]);

  const handleToggleHistory = useCallback(() => {
    if (!state.historyOpen) {
      const conversationId = conversationIdRef.current;
      if (conversationId) {
        void pallyApi.recordActivityEvent({
          event_id: crypto.randomUUID(),
          event_type: "transcript_expanded",
          occurred_at: new Date().toISOString(),
          conversation_id: conversationId,
        }).catch((error: unknown) => console.error("Activity event failed", error));
      }
    }
    dispatch({ type: "history/toggle" });
  }, [state.historyOpen]);

  const isIdle = state.rec.kind === "idle";
  const isProcessing = state.rec.kind === "processing";
  const isRecording = state.rec.kind === "recording";
  const errorVisible = state.rec.kind === "error";
  const showChatBubble = (state.messages.length > 0 || isRecording || isProcessing) && !errorVisible;
  const historyCoversScreen = state.historyOpen && !isIdle;

  if (isRestoring) {
    return (
      <MobileShell>
        <PageLoader />
      </MobileShell>
    );
  }

  return (
    <MobileShell>
      <div className="absolute right-4 top-5 z-40">
        <UsageSummary subscription={subscription} usage={usage} />
      </div>
      {showChatBubble ? (
        <>
          <button aria-label="대화 종료" className="absolute left-4 top-[23px] z-50 grid size-[41px] place-items-center border-0 bg-transparent p-0" disabled={isClosing} onClick={() => { void handleSessionEnd(); }} type="button">
            <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 20 20">
              <path d="M4 4l12 12M16 4 4 16" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
            </svg>
          </button>
          <div className="absolute inset-x-0 top-0 z-10">
            <ChatBubble
              expanded={state.historyOpen}
              listening={isRecording}
              messages={state.messages}
              pendingUserTranscript={pendingUserTranscript}
              onToggleExpand={handleToggleHistory}
              thinking={isProcessing}
            />
          </div>
        </>
      ) : null}

      {!historyCoversScreen ? (
        <>
          <div className={`absolute left-1/2 -translate-x-1/2 ${showChatBubble ? "top-[382px]" : "top-[369px]"}`}>
            {hasRestoredPally ? (
              <PallyCanvas axes={axes} size={308} />
            ) : (
              <div className="flex size-[308px] flex-col items-center justify-center gap-3 text-caption-1 text-primary" role="status">
                Pally를 불러오지 못했어요.
                <button className="underline underline-offset-4" onClick={() => window.location.reload()} type="button">
                  다시 불러오기
                </button>
              </div>
            )}
          </div>
          <div className={`absolute left-1/2 z-20 -translate-x-1/2 ${showChatBubble ? "top-[690px]" : "top-[649px]"}`}>
            <TalkButton disabled={isClosing || isRestoring || !hasRestoredPally || quotaExhausted} onPressStart={handlePressStart} onPressStop={handlePressStop} rec={state.rec} />
          </div>
        </>
      ) : null}

      <div className="absolute bottom-[100px] inset-x-0 z-40 px-4">
        <Toast message={state.rec.kind === "error" ? state.rec.message : ""} onDismiss={() => dispatch({ type: "rec/dismissError" })} visible={errorVisible} />
        <Toast message={warning ?? ""} onDismiss={() => setWarning(null)} visible={warning !== null} />
      </div>

      {!showChatBubble ? <BottomNav /> : null}
      {limitDialogOpen ? (
        <ConfirmDialog
          body="오늘 사용할 수 있는 무료 대화를 모두 사용했어요. 다음 KST 자정에 다시 충전돼요."
          confirmLabel="확인"
          onCancel={() => setLimitDialogOpen(false)}
          onConfirm={() => setLimitDialogOpen(false)}
          title="오늘의 대화를 모두 사용했어요"
        />
      ) : null}
    </MobileShell>
  );
}
