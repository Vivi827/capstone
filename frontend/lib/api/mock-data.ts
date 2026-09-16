import { DEFAULT_AXES } from "@/lib/types/character";

import type {
  Conversation,
  ConversationTurn,
  TurnResponse,
  UsageQuota,
  UserProfile,
} from "@/lib/api/contracts";

export const MOCK_PROFILE: UserProfile = {
  id: "7e91c88f-80a9-4f4a-b0fa-53fcb55e9987",
  display_name: "",
  english_level: "B1",
  onboarding_completed: false,
  traits: [],
  avatar_url: null,
  created_at: "2026-08-01T09:00:00Z",
  updated_at: "2026-08-01T09:00:00Z",
};

export const MOCK_QUOTA: UsageQuota = {
  remaining_turns: 5,
  daily_limit: 5,
  exhausted: false,
  resets_at: "2026-08-01T15:00:00Z",
};

export const MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: "2e108d60-3355-4e5e-85f8-27691c63ea3f",
    status: "completed",
    title: "Talking about lunch",
    started_at: "2026-07-31T09:00:00Z",
    last_turn_at: "2026-07-31T09:09:30Z",
    completed_at: "2026-07-31T09:10:00Z",
    turn_count: 2,
    current_axes: {
      Formality: 42,
      Energy: 58,
      Intimacy: 61,
      Humor: 37,
      Curiosity: 45,
    },
  },
];

export const MOCK_TURNS: ConversationTurn[] = [
  {
    id: "fc7d35a2-f4c8-42fd-a22f-3ad9b55c09ba",
    conversation_id: MOCK_CONVERSATIONS[0].id,
    sequence: 1,
    status: "completed",
    user_transcript: "I had no lunch. I'm on a diet.",
    pally_text: "Oh no, you skipped lunch because you're on a diet? What would you like to eat later?",
    pally_audio_url: null,
    axes: MOCK_CONVERSATIONS[0].current_axes!,
    character: {
      tone_casual: 58,
      energy_level: 58,
      humor_level: 37,
    },
    feedback: [
      {
        original: "I had no lunch.",
        corrected: "I skipped lunch.",
        explanation_ko: "점심을 거른 상황에는 skipped lunch가 더 자연스러워요.",
      },
    ],
    feedback_pending: false,
    warnings: [],
    created_at: "2026-07-31T09:00:03Z",
  },
  {
    id: "a28b442f-326e-40eb-9074-bc505da62e15",
    conversation_id: MOCK_CONVERSATIONS[0].id,
    sequence: 2,
    status: "completed",
    user_transcript: "Maybe I will eat salad tonight.",
    pally_text: "A salad sounds refreshing. What do you like to put in it?",
    pally_audio_url: null,
    axes: MOCK_CONVERSATIONS[0].current_axes!,
    character: {
      tone_casual: 58,
      energy_level: 58,
      humor_level: 37,
    },
    feedback: [
      {
        original: "Maybe I will eat salad tonight.",
        corrected: "Maybe I'll have a salad tonight.",
        explanation_ko: "식사 메뉴를 말할 때는 have a salad가 더 자연스러워요.",
      },
    ],
    feedback_pending: false,
    warnings: [],
    created_at: "2026-07-31T09:04:03Z",
  },
];

export interface MockTurnScript {
  transcript: string;
  reply: string;
  axes: TurnResponse["axes"];
  character: TurnResponse["character"];
  feedback: TurnResponse["feedback"];
}

export const MOCK_TURN_SCRIPTS: readonly MockTurnScript[] = [
  {
    transcript: "My bestie and I watch it yesterday and we was dying laughing.",
    reply: "Oh! You and your bestie watched it yesterday, and you were dying laughing? What was so funny?",
    axes: { Formality: 20, Energy: 72, Intimacy: 68, Humor: 74, Curiosity: 38 },
    character: { tone_casual: 80, energy_level: 72, humor_level: 74 },
    feedback: [
      {
        original: "My bestie and I watch it yesterday and we was dying laughing.",
        corrected: "My bestie and I watched it yesterday, and we were dying laughing.",
        explanation_ko: "어제 있었던 일이므로 watch는 watched, we 다음에는 were를 사용해요.",
      },
    ],
  },
  {
    transcript: "Could you tell me how I can sound more natural?",
    reply: "Of course! You already sound clear, and using shorter phrases can make you sound even more natural. What topic do you want to practice?",
    axes: { Formality: 64, Energy: 48, Intimacy: 57, Humor: 24, Curiosity: 82 },
    character: { tone_casual: 36, energy_level: 48, humor_level: 24 },
    feedback: [],
  },
  {
    transcript: "I am interesting in learning new slang.",
    reply: "Nice! You're interested in learning new slang. Is there an expression you've heard recently?",
    axes: { Formality: 43, Energy: 61, Intimacy: 63, Humor: 46, Curiosity: 75 },
    character: { tone_casual: 57, energy_level: 61, humor_level: 46 },
    feedback: [
      {
        original: "I am interesting in learning new slang.",
        corrected: "I am interested in learning new slang.",
        explanation_ko: "내가 관심을 느끼는 상태이므로 interesting이 아니라 interested를 사용해요.",
      },
    ],
  },
];

export const MOCK_SILENT_AUDIO_URL =
  "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

export function createEmptyConversation(id: string, now: string): Conversation {
  return {
    id,
    status: "active",
    title: null,
    started_at: now,
    last_turn_at: null,
    completed_at: null,
    turn_count: 0,
    current_axes: { ...DEFAULT_AXES },
  };
}
