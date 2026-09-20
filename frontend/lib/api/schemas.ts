import { z } from "zod";

export const axesSchema = z.object({
  Formality: z.number().min(0).max(100),
  Energy: z.number().min(0).max(100),
  Intimacy: z.number().min(0).max(100),
  Humor: z.number().min(0).max(100),
  Curiosity: z.number().min(0).max(100),
});

const characterSchema = z.object({
  tone_casual: z.number().min(0).max(100),
  energy_level: z.number().min(0).max(100),
  humor_level: z.number().min(0).max(100),
});

const feedbackSchema = z.object({
  id: z.string().optional(),
  original: z.string(),
  corrected: z.string(),
  explanation_ko: z.string(),
});

const warningSchema = z.object({
  code: z.enum(["tts_failed", "feedback_failed"]),
  message: z.string(),
});

const conversationSchema = z.object({
  id: z.string().uuid(),
  status: z.enum(["active", "completed"]),
  title: z.string().nullable(),
  started_at: z.string(),
  last_turn_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  turn_count: z.number().int().nonnegative(),
  current_axes: axesSchema.optional(),
  reopened_at: z.string().nullable().optional(),
  reopen_count: z.number().int().nonnegative().optional(),
});

export const profileResponseSchema = z.object({
  profile: z.object({
    id: z.string().uuid(),
    display_name: z.string(),
    english_level: z.enum(["A2", "B1", "B2", "C1"]),
    onboarding_completed: z.boolean(),
    traits: z.array(z.string()),
    avatar_url: z.string().url().nullable(),
    created_at: z.string(),
    updated_at: z.string(),
  }),
});

export const profileAvatarResponseSchema = z.object({
  avatar_url: z.string().url().nullable(),
});

export const conversationResponseSchema = z.object({ conversation: conversationSchema });

export const conversationMutationResponseSchema = z.object({
  conversation: conversationSchema.partial().required({ id: true, status: true }),
});

export const conversationListResponseSchema = z.object({
  items: z.array(conversationSchema.extend({
    title: z.string().nullable(),
    started_at: z.string(),
    last_turn_at: z.string().nullable(),
    completed_at: z.string().nullable(),
    turn_count: z.number().int().nonnegative(),
    feedback_count: z.number().int().nonnegative(),
    preview: z.string().nullable(),
  })),
  next_cursor: z.string().nullable(),
});

export const conversationDetailResponseSchema = z.object({
  conversation: conversationSchema.extend({
    title: z.string().nullable(),
    started_at: z.string(),
    last_turn_at: z.string().nullable(),
    completed_at: z.string().nullable(),
    turn_count: z.number().int().nonnegative(),
  }),
  turns: z.array(z.object({
    id: z.string().uuid(),
    sequence: z.number().int().positive(),
    status: z.enum(["processing", "completed", "partial", "failed"]),
    user_transcript: z.string().nullable(),
    pally_text: z.string().nullable(),
    feedback: z.array(feedbackSchema),
    feedback_pending: z.boolean(),
    created_at: z.string(),
  })),
  next_cursor: z.string().nullable(),
});

export const turnResponseSchema = z.object({
  conversation_id: z.string().uuid(),
  turn_id: z.string().uuid().nullable(),
  status: z.enum(["completed", "partial"]),
  replayed: z.boolean(),
  user: z.object({ transcript: z.string() }),
  pally: z.object({ text: z.string(), audio: z.string().nullable() }),
  axes: axesSchema,
  character: characterSchema,
  feedback: z.array(feedbackSchema),
  feedback_pending: z.boolean(),
  warnings: z.array(warningSchema),
  quota: z.object({
    used_turns: z.number().int().nonnegative().optional(),
    remaining_turns: z.number().int().nonnegative().nullable(),
    daily_limit: z.number().int().positive().nullable(),
    exhausted: z.boolean(),
    resets_at: z.string(),
  }).optional(),
  created_at: z.string().nullable(),
});

export const usageResponseSchema = z.object({
  plan: z.enum(["free", "pro"]),
  date: z.string(),
  timezone: z.literal("Asia/Seoul"),
  used_turns: z.number().int().nonnegative(),
  remaining_turns: z.number().int().nonnegative().nullable(),
  daily_limit: z.number().int().positive().nullable(),
  reset_at: z.string(),
});

export const achievementsResponseSchema = z.object({
  date: z.string(),
  timezone: z.literal("Asia/Seoul"),
  streak_count: z.number().int().nonnegative(),
  daily_tasks: z.array(z.object({
    id: z.string(),
    title: z.string(),
    description: z.string(),
    status: z.enum(["completed", "default"]),
    completed_at: z.string().nullable(),
  })).length(3),
});

export const billingProductsResponseSchema = z.object({
  test_mode: z.boolean(),
  products: z.array(z.object({
    id: z.string(),
    name: z.string(),
    interval: z.enum(["month", "year"]),
    amount_minor: z.number().int().nonnegative(),
    currency: z.string(),
    display_price: z.string(),
    trial_days: z.number().int().nonnegative(),
  })),
});

export const checkoutResponseSchema = z.object({
  checkout: z.object({
    product_id: z.string(),
    checkout_url: z.string().url(),
    expires_at: z.string(),
  }),
});

export const subscriptionResponseSchema = z.object({
  subscription: z.object({
    plan: z.enum(["free", "pro"]),
    status: z.string(),
    entitled: z.boolean(),
    product_id: z.string().nullable(),
    current_period_end: z.string().nullable(),
    will_renew: z.boolean(),
    entitlements: z.array(z.string()),
    updated_at: z.string().nullable(),
  }),
});

export const deleteAccountResponseSchema = z.object({
  status: z.literal("deleted"),
});

export const errorResponseSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string().optional(),
    details: z.record(z.string(), z.unknown()).optional(),
  }),
});

export const recordedEventResponseSchema = z.object({ recorded: z.literal(true) });
