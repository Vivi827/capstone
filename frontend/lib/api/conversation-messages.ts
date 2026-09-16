import type { ConversationTurn } from "@/lib/api/contracts";
import type { Message } from "@/lib/types/message";

export function conversationTurnsToMessages(
  conversationId: string,
  turns: readonly ConversationTurn[],
): Message[] {
  const roleOrder: Record<Message["role"], number> = { user: 0, pally: 1 };
  const sequencedMessages = turns.flatMap((turn) => {
    const messages: Array<{ message: Message; sequence: number }> = [];
    if (turn.user_transcript) {
      messages.push({
        message: {
          id: `${turn.id}-user`,
          sessionId: conversationId,
          role: "user",
          transcript: turn.user_transcript,
          createdAt: turn.created_at,
        },
        sequence: turn.sequence,
      });
    }
    if (turn.pally_text) {
      messages.push({
        message: {
          id: `${turn.id}-pally`,
          sessionId: conversationId,
          role: "pally",
          transcript: turn.pally_text,
          createdAt: turn.created_at,
        },
        sequence: turn.sequence,
      });
    }
    return messages;
  });

  return sequencedMessages
    .sort((left, right) => (
      left.message.createdAt.localeCompare(right.message.createdAt)
      || roleOrder[left.message.role] - roleOrder[right.message.role]
      || left.sequence - right.sequence
      || left.message.id.localeCompare(right.message.id)
    ))
    .map(({ message }) => message);
}
