/**
 * Phase 1A — conversation state machine.
 *
 * Single reducer covers:
 *   1. sessionId bootstrap (set once on first client mount per D-16)
 *   2. Rec state transitions per D-13:
 *        idle → recording → processing → speaking → idle
 *        idle → error (permission-denied | generic) → (next tap) → idle
 *   3. History sheet visibility (CHAT-01 chevron toggle)
 *
 * All states are discriminated unions so TS exhaustiveness catches missing
 * transitions at compile time.
 */

import type { Message } from '@/lib/types/message';

export type RecState =
  | { kind: 'idle' }
  | { kind: 'recording'; startedAt: number }
  | { kind: 'processing' }
  | { kind: 'speaking' }
  | { kind: 'error'; reason: 'permission-denied' | 'generic'; message: string };

export interface ConversationState {
  sessionId: string | null;
  messages: Message[];
  rec: RecState;
  historyOpen: boolean;
}

export type Action =
  | { type: 'sessionId/set'; id: string }
  | { type: 'rec/start' }
  | { type: 'rec/stop' }
  | { type: 'rec/processed'; userMsg: Message; pallyMsg: Message }
  | { type: 'rec/speakingDone' }
  | { type: 'rec/error'; reason: 'permission-denied' | 'generic'; message: string }
  | { type: 'rec/dismissError' }
  | { type: 'history/toggle' }
  | { type: 'session/end'; newId: string };

export const initialState: ConversationState = {
  sessionId: null,
  messages: [],
  rec: { kind: 'idle' },
  historyOpen: false,
};

export function reducer(state: ConversationState, action: Action): ConversationState {
  switch (action.type) {
    case 'sessionId/set':
      return { ...state, sessionId: action.id };
    case 'rec/start':
      return { ...state, rec: { kind: 'recording', startedAt: Date.now() } };
    case 'rec/stop':
      return { ...state, rec: { kind: 'processing' } };
    case 'rec/processed':
      return {
        ...state,
        messages: [...state.messages, action.userMsg, action.pallyMsg],
        rec: { kind: 'speaking' },
      };
    case 'rec/speakingDone':
      return { ...state, rec: { kind: 'idle' } };
    case 'rec/error':
      return {
        ...state,
        rec: { kind: 'error', reason: action.reason, message: action.message },
      };
    case 'rec/dismissError':
      // Tap-to-dismiss returns to idle without altering messages
      return state.rec.kind === 'error' ? { ...state, rec: { kind: 'idle' } } : state;
    case 'history/toggle':
      return { ...state, historyOpen: !state.historyOpen };
    case 'session/end':
      return {
        sessionId: action.newId,
        messages: [],
        rec: { kind: 'idle' },
        historyOpen: false,
      };
    default: {
      // Exhaustiveness — fails the build if a new Action variant is added without a case
      const exhaustive: never = action;
      throw new Error(`Unhandled conversation action: ${JSON.stringify(exhaustive)}`);
    }
  }
}
