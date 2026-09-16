import { pallyApi } from "@/lib/api";
import type { FeedbackItem } from "@/lib/api";

export function recordFeedbackItemOpened(conversationId: string, item: FeedbackItem): Promise<void> {
  return pallyApi.recordActivityEvent({
    event_id: crypto.randomUUID(),
    event_type: "feedback_item_opened",
    occurred_at: new Date().toISOString(),
    conversation_id: conversationId,
    ...(item.id ? { feedback_item_id: item.id } : {}),
  });
}
