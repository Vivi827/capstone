import type { z } from "zod";

import type {
  ActivityEventInput,
  DeleteAccountInput,
  CheckoutInput,
  GetConversationInput,
  ListConversationsInput,
  OnboardingInput,
  PallyApi,
  TurnInput,
  UpdateProfileInput,
} from "@/lib/api/contracts";
import { PallyApiError } from "@/lib/api/contracts";
import {
  achievementsResponseSchema,
  deleteAccountResponseSchema,
  billingProductsResponseSchema,
  checkoutResponseSchema,
  conversationDetailResponseSchema,
  conversationListResponseSchema,
  conversationMutationResponseSchema,
  conversationResponseSchema,
  errorResponseSchema,
  profileResponseSchema,
  profileAvatarResponseSchema,
  recordedEventResponseSchema,
  subscriptionResponseSchema,
  turnResponseSchema,
  usageResponseSchema,
} from "@/lib/api/schemas";
import { supabase } from "@/lib/supabase/client";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;

function createIdempotencyKey(): string {
  return crypto.randomUUID();
}

async function getAccessToken(): Promise<string> {
  const { data, error } = await supabase.auth.getSession();
  if (error) throw new PallyApiError(401, "unauthorized", error.message);
  const token = data.session?.access_token;
  if (!token) throw new PallyApiError(401, "unauthorized", "로그인이 필요해요.");
  return token;
}

type RequestOptions<TSchema extends z.ZodType> = {
  schema: TSchema;
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: BodyInit;
  contentType?: "application/json";
  idempotencyKey?: string;
};

async function apiRequest<TSchema extends z.ZodType>(path: string, options: RequestOptions<TSchema>): Promise<z.infer<TSchema>> {
  if (!backendUrl) throw new PallyApiError(503, "service_unavailable", "NEXT_PUBLIC_BACKEND_URL이 설정되지 않았어요.");

  const token = await getAccessToken();
  const headers = new Headers({ Authorization: `Bearer ${token}` });
  if (options.contentType) headers.set("Content-Type", options.contentType);
  if (options.idempotencyKey) headers.set("Idempotency-Key", options.idempotencyKey);

  const response = await fetch(`${backendUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body,
  });

  const payload: unknown = await response.json().catch((error: unknown) => {
    throw new PallyApiError(502, "invalid_response", error instanceof Error ? error.message : "서버 응답을 읽지 못했어요.");
  });

  if (!response.ok) {
    const parsedError = errorResponseSchema.safeParse(payload);
    if (!parsedError.success) {
      throw new PallyApiError(response.status, "invalid_response", `서버 오류 응답 형식이 올바르지 않아요. (${response.status})`);
    }
    throw new PallyApiError(
      response.status,
      parsedError.data.error.code,
      parsedError.data.error.message,
      parsedError.data.error.request_id,
    );
  }

  const parsed = options.schema.safeParse(payload);
  if (!parsed.success) {
    console.error("API response validation failed", { path, issues: parsed.error.issues });
    throw new PallyApiError(502, "invalid_response", "서버 응답 형식이 앱과 맞지 않아요.");
  }
  return parsed.data;
}

function queryString(input: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(input)) {
    if (value !== undefined) params.set(key, String(value));
  }
  const value = params.toString();
  return value ? `?${value}` : "";
}

export const httpPallyApi: PallyApi = {
  getProfile: () => apiRequest("/api/profile", { schema: profileResponseSchema }),

  getProfileAvatar: () => apiRequest("/api/profile/avatar", { schema: profileAvatarResponseSchema }),

  onboard: (input: OnboardingInput) => apiRequest("/api/onboarding", {
    schema: profileResponseSchema,
    method: "POST",
    contentType: "application/json",
    idempotencyKey: createIdempotencyKey(),
    body: JSON.stringify(input),
  }),

  updateProfile: (input: UpdateProfileInput) => apiRequest("/api/profile", {
    schema: profileResponseSchema,
    method: "PATCH",
    contentType: "application/json",
    body: JSON.stringify(input),
  }),

  createConversation: (idempotencyKey: string) => apiRequest("/api/conversations", {
    schema: conversationResponseSchema,
    method: "POST",
    idempotencyKey,
  }),

  async createTurn(conversationId: string, input: TurnInput) {
    const formData = new FormData();
    const extension = input.audio.type.includes("wav") ? "wav" : input.audio.type.includes("mp4") ? "mp4" : "webm";
    formData.append("audio", input.audio, `recording.${extension}`);
    return apiRequest(`/api/conversations/${encodeURIComponent(conversationId)}/turns`, {
      schema: turnResponseSchema,
      method: "POST",
      idempotencyKey: input.idempotency_key,
      body: formData,
    });
  },

  completeConversation: (conversationId: string) => apiRequest(`/api/conversations/${encodeURIComponent(conversationId)}/complete`, {
    schema: conversationMutationResponseSchema,
    method: "POST",
    idempotencyKey: createIdempotencyKey(),
  }),

  reopenConversation: (conversationId: string) => apiRequest(`/api/conversations/${encodeURIComponent(conversationId)}/reopen`, {
    schema: conversationMutationResponseSchema,
    method: "POST",
    idempotencyKey: createIdempotencyKey(),
  }),

  listConversations(input: ListConversationsInput = {}) {
    return apiRequest(`/api/conversations${queryString({ cursor: input.cursor, limit: input.limit, status: input.status })}`, { schema: conversationListResponseSchema });
  },

  getConversation(conversationId: string, input: GetConversationInput = {}) {
    return apiRequest(`/api/conversations/${encodeURIComponent(conversationId)}${queryString({ cursor: input.cursor, limit: input.limit })}`, {
      schema: conversationDetailResponseSchema,
    });
  },

  getUsage: () => apiRequest("/api/usage", { schema: usageResponseSchema }),

  async recordActivityEvent(input: ActivityEventInput) {
    await apiRequest("/api/activity-events", {
      schema: recordedEventResponseSchema,
      method: "POST",
      contentType: "application/json",
      idempotencyKey: createIdempotencyKey(),
      body: JSON.stringify(input),
    });
  },

  getAchievements: () => apiRequest("/api/achievements", { schema: achievementsResponseSchema }),

  getBillingProducts: () => apiRequest("/api/billing/products", { schema: billingProductsResponseSchema }),

  createCheckout: (input: CheckoutInput) => apiRequest("/api/billing/checkout", {
    schema: checkoutResponseSchema,
    method: "POST",
    contentType: "application/json",
    idempotencyKey: createIdempotencyKey(),
    body: JSON.stringify(input),
  }),

  getSubscription: () => apiRequest("/api/subscription", { schema: subscriptionResponseSchema }),

  refreshSubscription: () => apiRequest("/api/subscription/refresh", {
    schema: subscriptionResponseSchema,
    method: "POST",
    idempotencyKey: createIdempotencyKey(),
  }),

  deleteAccount: (input: DeleteAccountInput) => apiRequest("/api/account", {
    schema: deleteAccountResponseSchema,
    method: "DELETE",
    contentType: "application/json",
    body: JSON.stringify(input),
  }),

};
