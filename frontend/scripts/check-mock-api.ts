import { rejects } from "node:assert/strict";

import { mockPallyApi, resetMockPallyApi } from "../lib/api/mock-client";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

async function main(): Promise<void> {
  resetMockPallyApi();

  const initialProfile = await mockPallyApi.getProfile();
  assert(!initialProfile.profile.onboarding_completed, "Profile must start before onboarding");

  const onboarded = await mockPallyApi.onboard({
    display_name: "Claire",
    english_level: "B2",
  });
  assert(onboarded.profile.display_name === "Claire", "Onboarding must save display_name");
  assert(onboarded.profile.english_level === "B2", "Onboarding must save english_level");

  const updated = await mockPallyApi.updateProfile({ english_level: "C1" });
  assert(updated.profile.english_level === "C1", "Profile update must save english_level");

  const conversationKey = crypto.randomUUID();
  const created = await mockPallyApi.createConversation(conversationKey);
  const repeatedCreate = await mockPallyApi.createConversation(conversationKey);
  assert(created.conversation.id === repeatedCreate.conversation.id, "Conversation creation must be idempotent");

  const turnKey = crypto.randomUUID();
  const audio = new Blob([new Uint8Array([1, 2, 3])], { type: "audio/wav" });
  const turn = await mockPallyApi.createTurn(created.conversation.id, {
    audio,
    idempotency_key: turnKey,
  });
  const repeatedTurn = await mockPallyApi.createTurn(created.conversation.id, {
    audio,
    idempotency_key: turnKey,
  });
  assert(turn.turn_id === repeatedTurn.turn_id, "Turn creation must be idempotent");
  assert(!turn.replayed && repeatedTurn.replayed, "An idempotent retry must be marked as replayed");
  assert(!turn.feedback_pending, "A successful feedback result must not be pending");
  assert(turn.quota?.remaining_turns === 4, "A successful turn must consume one quota unit");
  assert(repeatedTurn.quota?.remaining_turns === 4, "An idempotent replay must not consume quota again");

  const detail = await mockPallyApi.getConversation(created.conversation.id);
  assert(detail.turns.length === 1, "Conversation detail must include the created turn");
  assert(detail.turns[0].feedback.length > 0, "Mock turn must expose inline feedback");

  const completed = await mockPallyApi.completeConversation(created.conversation.id);
  assert(completed.conversation.status === "completed", "Conversation must become completed");

  const list = await mockPallyApi.listConversations({ status: "completed" });
  assert(list.items.some((item) => item.id === created.conversation.id), "Completed conversation must appear in history");

  const products = await mockPallyApi.getBillingProducts();
  assert(products.products.length === 2, "Billing products must come from the API contract");
  const subscription = await mockPallyApi.getSubscription();
  assert(!subscription.subscription.entitled, "Mock subscription must start on the free plan");
  const checkout = await mockPallyApi.createCheckout({
    product_id: products.products[0].id,
    success_url: "https://example.com/settings/plans?checkout=success",
    cancel_url: "https://example.com/settings/plans?checkout=cancel",
  }, initialProfile.profile.id);
  assert(checkout.checkout.product_id === products.products[0].id, "Checkout must preserve the selected product");

  const deletion = await mockPallyApi.deleteAccount({ confirmation: "회원탈퇴" });
  assert(deletion.status === "deleted", "Account deletion must complete immediately");
  await rejects(() => mockPallyApi.getProfile(), "Deleted accounts must not access profile data");

  resetMockPallyApi();
  console.log("Mock API contract check passed.");
}

main().catch((error: unknown) => {
  console.error("Mock API contract check failed:", error);
  process.exit(1);
});
