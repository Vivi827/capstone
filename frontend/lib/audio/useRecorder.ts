'use client';

import { useCallback, useRef } from 'react';
import { pickMimeType } from './pickMimeType';

// 30s cap per CONTEXT D-08. Long enough for a single conversational turn,
// short enough to bound MediaRecorder memory + abuse.
const MAX_DURATION_MS = 30_000;

// Inline copy per UI-SPEC § Copywriting Contract → "Error and permission states".
const ERR_NO_MIME = '이 브라우저는 음성 녹음을 지원하지 않아요.';
const ERR_MIC_ACCESS = '마이크에 접근할 수 없어요.';

export interface RecorderHandlers {
  onStart: () => void;
  onStop: (blob: Blob | null) => void;
  onPermissionDenied: () => void;
  onError: (message: string) => void;
}

export interface RecorderControls {
  start: () => Promise<void>;
  stop: () => void;
}

export function useRecorder(handlers: RecorderHandlers): RecorderControls {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const mimeRef = useRef<string | null>(null);

  const stop = useCallback((): void => {
    // Pitfall 5: clear the 30s timer before calling MediaRecorder.stop()
    // to avoid double-stop DOMException when user taps early.
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const r = recorderRef.current;
    if (r && r.state !== 'inactive') {
      r.stop();
    }
  }, []);

  const start = useCallback(async (): Promise<void> => {
    const mime = pickMimeType();
    if (!mime) {
      handlers.onError(ERR_NO_MIME);
      return;
    }
    mimeRef.current = mime;

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      // Surface — never swallow (CLAUDE.md §7).
      const name = err instanceof DOMException ? err.name : '';
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        handlers.onPermissionDenied();
      } else {
        handlers.onError(ERR_MIC_ACCESS);
      }
      return;
    }
    streamRef.current = stream;

    const recorder = new MediaRecorder(stream, { mimeType: mime });
    recorderRef.current = recorder;
    chunksRef.current = [];

    recorder.ondataavailable = (e: BlobEvent) => {
      if (e.data.size > 0) {
        chunksRef.current.push(e.data);
      }
    };

    recorder.onstop = () => {
      const captured = chunksRef.current;
      const finalMime = mimeRef.current ?? mime;
      const blob = captured.length > 0 ? new Blob(captured, { type: finalMime }) : null;

      // Pitfall 4: stop tracks so the browser mic indicator clears.
      const s = streamRef.current;
      if (s) {
        for (const t of s.getTracks()) {
          t.stop();
        }
      }
      streamRef.current = null;
      recorderRef.current = null;
      chunksRef.current = [];

      handlers.onStop(blob);
    };

    recorder.start(250); // timeslice for iOS Safari: guarantees ondataavailable fires
    handlers.onStart();

    // 30s auto-stop (D-08). Cleared by stop() if user taps early (Pitfall 5).
    timerRef.current = window.setTimeout(() => {
      stop();
    }, MAX_DURATION_MS);
  }, [handlers, stop]);

  return { start, stop };
}
