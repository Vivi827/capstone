import type { Axes } from "@/lib/types/character";
import type { Level } from "@/lib/types/session";

export type ConversationStatus = "active" | "completed";
export type TurnStatus = "processing" | "completed" | "partial" | "failed";

export interface CharacterParams {
  tone_casual: number;
  energy_level: number;
  humor_level: number;
}

export interface UserProfile {
  id: string;
  display_name: string;
  english_level: Level;
  onboarding_completed: boolean;
  traits: string[];
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  status: ConversationStatus;
  title: string | null;
  started_at: string;
  last_turn_at: string | null;
  completed_at: string | null;
  turn_count: number;
  current_axes?: Axes;
  reopened_at?: string | null;
  reopen_count?: number;
}

export interface ConversationListItem extends Conversation {
  feedback_count: number;
  preview: string | null;
}

export interface FeedbackItem {
  id?: string;
  original: string;
  corrected: string;
  explanation_ko: string;
}

export type ApiWarningCode = "tts_failed" | "feedback_failed";

export interface ApiWarning {
  code: ApiWarningCode;
  message: string;
}

export interface ConversationTurn {
  id: string;
  conversation_id?: string;
  sequence: number;
  status: TurnStatus;
  user_transcript: string | null;
  pally_text: string | null;
  pally_audio_url?: string | null;
  axes?: Axes | null;
  character?: CharacterParams | null;
  feedback: FeedbackItem[];
  feedback_pending: boolean;
  warnings?: ApiWarning[];
  created_at: string;
}

export interface UsageQuota {
  used_turns?: number;
  remaining_turns: number;
  daily_limit: number;
  exhausted: boolean;
  resets_at: string;
}

export interface ProfileResponse {
  profile: UserProfile;
}

export interface ProfileAvatarResponse {
  avatar_url: string | null;
}

export interface ConversationResponse {
  conversation: Conversation;
}

export interface ConversationMutationResponse {
  conversation: Pick<Conversation, "id" | "status"> & Partial<Conversation>;
}

export interface ConversationListResponse {
  items: ConversationListItem[];
  next_cursor: string | null;
}

export interface ConversationDetailResponse {
  conversation: Conversation;
  turns: ConversationTurn[];
  next_cursor: string | null;
}

export interface TurnResponse {
  conversation_id: string;
  turn_id: string | null;
  status: "completed" | "partial";
  replayed: boolean;
  user: {
    transcript: string;
  };
  pally: {
    text: string;
    audio: string | null;
  };
  axes: Axes;
  character: CharacterParams;
  feedback: FeedbackItem[];
  feedback_pending: boolean;
  warnings: ApiWarning[];
  quota?: UsageQuota;
  created_at: string | null;
}

export interface UsageResponse {
  plan: "free";
  date: string;
  timezone: "Asia/Seoul";
  used_turns: number;
  remaining_turns: number;
  daily_limit: number;
  reset_at: string;
}

export type BillingInterval = "month" | "year";

export interface BillingProduct {
  id: string;
  name: string;
  interval: BillingInterval;
  amount_minor: number;
  currency: string;
  display_price: string;
  trial_days: number;
}

export interface BillingProductsResponse {
  products: BillingProduct[];
}

export interface CheckoutInput {
  product_id: string;
  success_url: string;
  cancel_url: string;
}

export interface CheckoutResponse {
  checkout: {
    product_id: string;
    checkout_url: string;
    expires_at: string;
  };
}

export interface Subscription {
  plan: "free" | "pro";
  status: string;
  entitled: boolean;
  product_id: string | null;
  current_period_end: string | null;
  will_renew: boolean;
  entitlements: string[];
  updated_at: string | null;
}

export interface SubscriptionResponse {
  subscription: Subscription;
}

export interface DeleteAccountInput {
  confirmation: "회원탈퇴";
}

export interface DeleteAccountResponse {
  status: "deleted";
}

export type ActivityEventType =
  | "app_session_started"
  | "conversation_detail_opened"
  | "transcript_expanded"
  | "feedback_item_opened"
  | "achievements_opened"
  | "profile_opened";

export interface ActivityEventInput {
  event_id: string;
  event_type: ActivityEventType;
  occurred_at: string;
  conversation_id?: string;
  feedback_item_id?: string;
}

export interface DailyTask {
  id: string;
  title: string;
  description: string;
  status: "completed" | "default";
  completed_at: string | null;
}

export interface AchievementsResponse {
  date: string;
  timezone: "Asia/Seoul";
  streak_count: number;
  daily_tasks: DailyTask[];
}

export interface OnboardingInput {
  display_name: string;
  english_level: Level;
}

export interface UpdateProfileInput {
  display_name?: string;
  english_level?: Level;
}

export interface TurnInput {
  audio: Blob;
  client_started_at?: string;
  idempotency_key: string;
}

export interface ListConversationsInput {
  cursor?: string;
  limit?: number;
  status?: ConversationStatus;
}

export interface GetConversationInput {
  cursor?: string;
  limit?: number;
}

export interface PallyApi {
  getProfile(): Promise<ProfileResponse>;
  getProfileAvatar(): Promise<ProfileAvatarResponse>;
  onboard(input: OnboardingInput): Promise<ProfileResponse>;
  updateProfile(input: UpdateProfileInput): Promise<ProfileResponse>;
  createConversation(idempotencyKey: string): Promise<ConversationResponse>;
  createTurn(conversationId: string, input: TurnInput): Promise<TurnResponse>;
  completeConversation(conversationId: string): Promise<ConversationMutationResponse>;
  reopenConversation(conversationId: string): Promise<ConversationMutationResponse>;
  listConversations(input?: ListConversationsInput): Promise<ConversationListResponse>;
  getConversation(conversationId: string, input?: GetConversationInput): Promise<ConversationDetailResponse>;
  getUsage(): Promise<UsageResponse>;
  recordActivityEvent(input: ActivityEventInput): Promise<void>;
  getAchievements(): Promise<AchievementsResponse>;
  getBillingProducts(): Promise<BillingProductsResponse>;
  createCheckout(input: CheckoutInput): Promise<CheckoutResponse>;
  getSubscription(): Promise<SubscriptionResponse>;
  refreshSubscription(): Promise<SubscriptionResponse>;
  deleteAccount(input: DeleteAccountInput): Promise<DeleteAccountResponse>;
}

export type ApiErrorCode =
  | "unauthorized"
  | "not_found"
  | "profile_not_found"
  | "invalid_audio"
  | "payload_too_large"
  | "validation_error"
  | "speech_not_recognized"
  | "quota_exceeded"
  | "conflict"
  | "conversation_closed"
  | "idempotency_conflict"
  | "persistence_failed"
  | "service_unavailable";

export class PallyApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string;

  constructor(status: number, code: string, message: string, requestId = createRequestId()) {
    super(message);
    this.name = "PallyApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

function createRequestId(): string {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `req_${suffix}`;
}
