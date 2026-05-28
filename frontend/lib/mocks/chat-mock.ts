/**
 * Phase 1A → Phase 2 transport for /api/chat.
 *
 * This is the single swap point between the frontend conversation flow and
 * the backend chat contract. It uses the real backend URL configured in
 * `NEXT_PUBLIC_BACKEND_URL`.
 */

import type { ChatRequest, ChatResponse } from '@/lib/types/chat';

export async function mockChat(req: ChatRequest): Promise<ChatResponse> {
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!backendUrl) {
    throw new Error('NEXT_PUBLIC_BACKEND_URL is not configured');
  }

  const response = await fetch(`${backendUrl}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Backend /api/chat failed ${response.status}: ${text}`);
  }

  return (await response.json()) as ChatResponse;
}
