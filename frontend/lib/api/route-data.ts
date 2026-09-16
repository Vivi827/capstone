import type {
  AchievementsResponse,
  ConversationDetailResponse,
  ConversationListResponse,
  ProfileResponse,
  SubscriptionResponse,
  UsageResponse,
} from "@/lib/api/contracts";
import { PallyApiError } from "@/lib/api/contracts";
import { pallyApi } from "@/lib/api";
import { clearUser, invalidate, peek, prefetch, read, write } from "@/lib/api/query-cache";
import { supabase } from "@/lib/supabase/client";

const USAGE_TTL_MS = 15_000;
const CONVERSATION_TTL_MS = 30_000;
const ROUTE_DATA_TTL_MS = 60_000;

const CACHE_KEYS = {
  achievements: "achievements",
  conversation: "conversation:",
  history: "history:",
  profile: "profile",
  subscription: "subscription",
  usage: "usage",
} as const;

function cursorKey(cursor?: string): string {
  return cursor ?? "first";
}

export async function getCurrentUserId(): Promise<string> {
  const { data, error } = await supabase.auth.getSession();
  if (error) throw new PallyApiError(401, "unauthorized", error.message);
  if (!data.session) throw new PallyApiError(401, "unauthorized", "로그인이 필요해요.");
  return data.session.user.id;
}

export function loadUsage(userId: string): Promise<UsageResponse> {
  return read(userId, CACHE_KEYS.usage, USAGE_TTL_MS, () => pallyApi.getUsage());
}

export function loadSubscription(userId: string): Promise<SubscriptionResponse> {
  return read(userId, CACHE_KEYS.subscription, ROUTE_DATA_TTL_MS, () => pallyApi.getSubscription());
}

export function loadProfile(userId: string): Promise<ProfileResponse> {
  return read(userId, CACHE_KEYS.profile, ROUTE_DATA_TTL_MS, () => pallyApi.getProfile());
}

export function cacheProfile(userId: string, response: ProfileResponse): void {
  write(userId, CACHE_KEYS.profile, ROUTE_DATA_TTL_MS, response);
}

export function loadAchievements(userId: string): Promise<AchievementsResponse> {
  return read(userId, CACHE_KEYS.achievements, ROUTE_DATA_TTL_MS, () => pallyApi.getAchievements());
}

export function loadHistoryPage(userId: string, cursor?: string): Promise<ConversationListResponse> {
  const key = `${CACHE_KEYS.history}${cursorKey(cursor)}`;
  return read(userId, key, ROUTE_DATA_TTL_MS, () => (
    pallyApi.listConversations({ status: "completed", cursor, limit: 20 })
  ));
}

export function loadLatestCompletedConversation(userId: string): Promise<ConversationListResponse> {
  const history = peek<ConversationListResponse>(userId, `${CACHE_KEYS.history}first`);
  if (history) return Promise.resolve(history);

  // Share history data on return visits; fetch only one summary on a cold home load.
  return read(userId, `${CACHE_KEYS.history}latest`, ROUTE_DATA_TTL_MS, () => (
    pallyApi.listConversations({ status: "completed", limit: 1 })
  ));
}

export function loadConversationPage(
  userId: string,
  conversationId: string,
  cursor?: string,
): Promise<ConversationDetailResponse> {
  const key = `${CACHE_KEYS.conversation}${conversationId}:${cursorKey(cursor)}`;
  return read(userId, key, CONVERSATION_TTL_MS, () => (
    pallyApi.getConversation(conversationId, { cursor, limit: 50 })
  ));
}

export function invalidateUsage(userId: string): void {
  invalidate(userId, CACHE_KEYS.usage);
}

export function invalidateProfile(userId: string): void {
  invalidate(userId, CACHE_KEYS.profile);
}

export function invalidateSubscription(userId: string): void {
  invalidate(userId, CACHE_KEYS.subscription);
}

export function invalidateConversationData(userId: string, conversationId?: string): void {
  invalidate(userId, CACHE_KEYS.history);
  if (conversationId) invalidate(userId, `${CACHE_KEYS.conversation}${conversationId}:`);
  invalidate(userId, CACHE_KEYS.achievements);
}

export function clearUserRouteData(userId: string): void {
  clearUser(userId);
}

export async function invalidateCurrentUserConversationData(conversationId?: string): Promise<void> {
  const userId = await getCurrentUserId();
  invalidateConversationData(userId, conversationId);
}

export async function prefetchRouteData(href: string, userId?: string): Promise<void> {
  const scope = userId ?? await getCurrentUserId();
  if (href.startsWith("/home")) {
    await Promise.all([
      loadLatestCompletedConversation(scope),
      prefetch(scope, CACHE_KEYS.usage, USAGE_TTL_MS, () => pallyApi.getUsage()),
      prefetch(scope, CACHE_KEYS.subscription, ROUTE_DATA_TTL_MS, () => pallyApi.getSubscription()),
    ]);
    return;
  }
  if (href.startsWith("/history")) {
    await prefetch(scope, `${CACHE_KEYS.history}first`, ROUTE_DATA_TTL_MS, () => (
      pallyApi.listConversations({ status: "completed", limit: 20 })
    ));
    return;
  }
  if (href.startsWith("/ranking")) {
    await prefetch(scope, CACHE_KEYS.achievements, ROUTE_DATA_TTL_MS, () => pallyApi.getAchievements());
    return;
  }
  if (href.startsWith("/my")) {
    await prefetch(scope, CACHE_KEYS.profile, ROUTE_DATA_TTL_MS, () => pallyApi.getProfile());
  }
}

type NetworkInformationLike = {
  effectiveType?: string;
  saveData?: boolean;
};

function canPrefetchOnCurrentNetwork(): boolean {
  const connection = (navigator as Navigator & { connection?: NetworkInformationLike }).connection;
  if (!connection) return false;
  if (connection.saveData) return false;
  return connection.effectiveType === "4g";
}

export function schedulePrimaryRoutePrefetch(userId: string): () => void {
  if (!canPrefetchOnCurrentNetwork()) return () => undefined;

  const run = () => {
    void Promise.allSettled([
      prefetchRouteData("/history/note", userId),
      prefetchRouteData("/ranking", userId),
      prefetchRouteData("/my", userId),
    ]).then((results) => {
      for (const result of results) {
        if (result.status === "rejected") console.error("Route data prefetch failed", result.reason);
      }
    });
  };

  const idleWindow = window as Window & {
    cancelIdleCallback?: (handle: number) => void;
    requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  };
  if (idleWindow.requestIdleCallback) {
    const handle = idleWindow.requestIdleCallback(run, { timeout: 2_000 });
    return () => {
      if (idleWindow.cancelIdleCallback) idleWindow.cancelIdleCallback(handle);
    };
  }

  const handle = window.setTimeout(run, 500);
  return () => window.clearTimeout(handle);
}
