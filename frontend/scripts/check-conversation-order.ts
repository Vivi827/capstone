import assert from "node:assert/strict";

import type { ConversationTurn } from "../lib/api/contracts";
import { conversationTurnsToMessages } from "../lib/api/conversation-messages";

const turns: ConversationTurn[] = [
  {
    id: "00000000-0000-0000-0000-000000000002",
    sequence: 2,
    status: "completed",
    user_transcript: "just working on my project",
    pally_text: null,
    feedback: [],
    feedback_pending: false,
    created_at: "2026-09-06T10:00:00+00:00",
  },
  {
    id: "00000000-0000-0000-0000-000000000001",
    sequence: 1,
    status: "completed",
    user_transcript: null,
    pally_text: "That's great you're focused on your project!",
    feedback: [],
    feedback_pending: false,
    created_at: "2026-09-06T10:00:00+00:00",
  },
  {
    id: "00000000-0000-0000-0000-000000000003",
    sequence: 3,
    status: "completed",
    user_transcript: "yeah but it's not a fun thing to do you know",
    pally_text: "Oh, I hear you; it's tough when your project feels more like a chore.",
    feedback: [],
    feedback_pending: false,
    created_at: "2026-09-06T10:01:00+00:00",
  },
];

const messages = conversationTurnsToMessages("00000000-0000-0000-0000-000000000000", turns);

assert.deepEqual(
  messages.map(({ role, transcript }) => [role, transcript]),
  [
    ["user", "just working on my project"],
    ["pally", "That's great you're focused on your project!"],
    ["user", "yeah but it's not a fun thing to do you know"],
    ["pally", "Oh, I hear you; it's tough when your project feels more like a chore."],
  ],
);

console.log("Conversation ordering checks passed.");
