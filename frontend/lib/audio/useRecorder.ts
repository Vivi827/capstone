'use client';

import { useCallback, useRef } from 'react';
import { pickMimeType } from './pickMimeType';

const MAX_DURATION_MS = 30_000;
const SPEECH_TRANSCRIPT_GRACE_MS = 900;

const ERR_NO_MIME = '이 브라우저는 음성 녹음을 지원하지 않아요.';
const ERR_MIC_ACCESS = '마이크에 접근할 수 없어요.';

export interface RecorderHandlers {
  onStart: () => void;
  /**
   * blob: recorded audio from MediaRecorder.
   * transcript: browser-recognized preview shown while the backend processes the turn.
   */
  onStop: (blob: Blob | null, transcript?: string) => void;
  onPermissionDenied: () => void;
  onError: (message: string) => void;
}

export interface RecorderControls {
  start: () => Promise<void>;
  stop: () => void;
  cancel: () => void;
}

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  readonly length: number;
  readonly isFinal: boolean;
  [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionEventLike {
  readonly results: {
    readonly length: number;
    [index: number]: SpeechRecognitionResultLike;
  };
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

interface SpeechRecognitionConstructorLike {
  new (): SpeechRecognitionLike;
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructorLike;
    webkitSpeechRecognition?: SpeechRecognitionConstructorLike;
  }
}

function getDesktopSpeechRecognitionCtor(): SpeechRecognitionConstructorLike | null {
  if (typeof window === 'undefined') return null;
  if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

export function useRecorder(handlers: RecorderHandlers): RecorderControls {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const mimeRef = useRef<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const finalizeTimerRef = useRef<number | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const speechTranscriptRef = useRef('');
  const discardRecordingRef = useRef(false);
  const startingRef = useRef(false);

  const cleanupStream = useCallback(() => {
    const stream = streamRef.current;
    if (stream) {
      for (const track of stream.getTracks()) {
        track.stop();
      }
    }
    streamRef.current = null;
  }, []);

  const stop = useCallback((): void => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    const recorder = recorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      const recognition = recognitionRef.current;
      if (recognition) {
        try {
          recognition.stop();
        } catch {
          // SpeechRecognition may already be stopped.
        }
      }
      cleanupStream();
      return;
    }

    const recognition = recognitionRef.current;
    if (recognition) {
      try {
        recognition.stop();
      } catch {
        // SpeechRecognition may already be stopped.
      }
    }

    try {
      recorder.requestData();
    } catch {
      // Some browsers do not support requestData while stopping.
    }
    recorder.stop();
  }, [cleanupStream]);

  const cancel = useCallback((): void => {
    if (finalizeTimerRef.current !== null) {
      window.clearTimeout(finalizeTimerRef.current);
      finalizeTimerRef.current = null;
    }
    discardRecordingRef.current = true;
    speechTranscriptRef.current = '';
    stop();
  }, [stop]);

  const start = useCallback(async (): Promise<void> => {
    if (startingRef.current || recorderRef.current?.state === 'recording') return;

    startingRef.current = true;
    discardRecordingRef.current = false;
    speechTranscriptRef.current = '';

    const mime = pickMimeType();
    if (!mime) {
      startingRef.current = false;
      handlers.onError(ERR_NO_MIME);
      return;
    }
    mimeRef.current = mime;

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: { ideal: 1 } },
      });
    } catch (err) {
      startingRef.current = false;
      const name = err instanceof DOMException ? err.name : '';
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        handlers.onPermissionDenied();
      } else {
        handlers.onError(ERR_MIC_ACCESS);
      }
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const SpeechRecognitionCtor = getDesktopSpeechRecognitionCtor();
    if (SpeechRecognitionCtor) {
      try {
        const recognition = new SpeechRecognitionCtor();
        recognition.lang = 'en-US';
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.onresult = (event) => {
          const parts: string[] = [];
          for (let i = 0; i < event.results.length; i++) {
            const transcript = event.results[i][0]?.transcript;
            if (transcript) parts.push(transcript);
          }
          speechTranscriptRef.current = parts.join(' ').trim();
        };
        recognition.onerror = () => {
          recognitionRef.current = null;
        };
        recognition.onend = () => {
          recognitionRef.current = null;
        };
        recognition.start();
        recognitionRef.current = recognition;
      } catch {
        recognitionRef.current = null;
      }
    }

    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType: mime });
    } catch (error) {
      startingRef.current = false;
      cleanupStream();
      console.error('MediaRecorder initialization failed.', error);
      handlers.onError(ERR_NO_MIME);
      return;
    }
    recorderRef.current = recorder;

    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    };

    recorder.onerror = () => {
      cleanupStream();
      recorderRef.current = null;
      chunksRef.current = [];
      handlers.onError(ERR_MIC_ACCESS);
    };

    recorder.onstop = () => {
      const captured = chunksRef.current;
      const finalMime = mimeRef.current ?? mime;
      const blob = captured.length > 0 ? new Blob(captured, { type: finalMime }) : null;
      const shouldDiscard = discardRecordingRef.current;

      cleanupStream();
      recorderRef.current = null;
      chunksRef.current = [];
      discardRecordingRef.current = false;

      if (shouldDiscard) {
        speechTranscriptRef.current = '';
        return;
      }

      finalizeTimerRef.current = window.setTimeout(() => {
        finalizeTimerRef.current = null;
        const transcript = speechTranscriptRef.current.trim();
        speechTranscriptRef.current = '';
        handlers.onStop(blob, transcript || undefined);
      }, SPEECH_TRANSCRIPT_GRACE_MS);
    };

    try {
      recorder.start(250);
    } catch (error) {
      startingRef.current = false;
      recorderRef.current = null;
      cleanupStream();
      console.error('MediaRecorder start failed.', error);
      handlers.onError(ERR_MIC_ACCESS);
      return;
    }
    startingRef.current = false;
    handlers.onStart();
    timerRef.current = window.setTimeout(() => {
      stop();
    }, MAX_DURATION_MS);
  }, [cleanupStream, handlers, stop]);

  return { start, stop, cancel };
}
