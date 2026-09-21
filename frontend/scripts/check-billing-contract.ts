import { deepEqual, equal, rejects } from "node:assert/strict";

import type {
  BillingCheckoutBlockedReason,
  BillingHistoryEntry,
  BillingOverviewResponse,
  PendingBillingOrder,
  Subscription,
} from "../lib/api/contracts";
import { mockPallyApi, resetMockPallyApi } from "../lib/api/mock-client";
import {
  billingHistoryEntrySchema,
  billingOverviewResponseSchema,
  pendingBillingOrderSchema,
} from "../lib/api/schemas";

const freeSubscription: Subscription = {
  plan: "free",
  status: "none",
  entitled: false,
  product_id: null,
  current_period_end: null,
  will_renew: false,
  entitlements: [],
  updated_at: null,
};

const approvedOrder: BillingHistoryEntry = {
  id: "86509154-3107-4f11-8878-eab353a588cb",
  product_id: "pro_monthly",
  amount: 9900,
  currency: "KRW",
  kind: "initial",
  trial_days: 0,
  status: "approved",
  created_at: "2026-09-20T02:00:00+00:00",
  approved_at: "2026-09-20T02:01:00+00:00",
};

const pendingOrder: PendingBillingOrder = {
  id: "7a22c058-5af9-4051-bb49-5578f63976ef",
  product_id: "pro_yearly",
  amount: 0,
  currency: "KRW",
  kind: "initial",
  trial_days: 7,
  status: "ready",
  created_at: "2026-09-20T11:00:00+09:00",
  expires_at: "2026-09-20T02:30:00Z",
};

const emptyOverview: BillingOverviewResponse = {
  subscription: freeSubscription,
  history: [],
  history_has_more: false,
  pending_order: null,
  checkout_blocked_reason: null,
};

function checkSchemas(): void {
  deepEqual(billingOverviewResponseSchema.parse(emptyOverview), emptyOverview);
  deepEqual(billingHistoryEntrySchema.parse(approvedOrder), approvedOrder);

  for (const kind of ["initial", "renewal"] as const) {
    for (const productId of ["pro_monthly", "pro_yearly"] as const) {
      equal(billingHistoryEntrySchema.safeParse({
        ...approvedOrder,
        product_id: productId,
        kind,
      }).success, true, "Supported products and billing kinds must parse");
    }
  }

  const trial = { ...approvedOrder, product_id: "pro_yearly", amount: 0, trial_days: 7 };
  equal(billingHistoryEntrySchema.safeParse(trial).success, true, "Zero-charge trials must parse");

  for (const status of ["preparing", "ready", "processing", "uncertain"] as const) {
    equal(billingOverviewResponseSchema.safeParse({
      ...emptyOverview,
      pending_order: { ...pendingOrder, status },
      checkout_blocked_reason: "payment_pending",
    }).success, true, "Every pending state must parse");
  }

  const blockedReasons: BillingCheckoutBlockedReason[] = [
    "subscription_active", "payment_pending", "renewal_active", "deactivation_pending",
  ];
  for (const reason of blockedReasons) {
    equal(billingOverviewResponseSchema.safeParse({
      ...emptyOverview,
      checkout_blocked_reason: reason,
    }).success, true, "Every checkout block reason must parse");
  }

  for (const status of ["active", "trialing", "canceled", "expired"] as const) {
    equal(billingOverviewResponseSchema.safeParse({
      ...emptyOverview,
      subscription: { ...freeSubscription, status },
      history: [approvedOrder, trial],
      history_has_more: true,
    }).success, true, "Existing subscription states and paginated history must parse");
  }

  const invalidCommonFields: Record<string, unknown>[] = [
    { id: "not-a-uuid" },
    { product_id: "pro_weekly" },
    { amount: -1 },
    { amount: 9.5 },
    { currency: "USD" },
    { kind: "refund" },
    { trial_days: 14 },
    { created_at: "not-a-date" },
    { created_at: "2026-09-20T02:00:00" },
    { created_at: "2026-02-30T02:00:00Z" },
  ];
  for (const invalidFields of invalidCommonFields) {
    equal(billingHistoryEntrySchema.safeParse({ ...approvedOrder, ...invalidFields }).success, false);
    equal(pendingBillingOrderSchema.safeParse({ ...pendingOrder, ...invalidFields }).success, false);
  }
  for (const status of ["ready", "failed", "cancelled"]) {
    equal(billingHistoryEntrySchema.safeParse({ ...approvedOrder, status }).success, false);
  }
  for (const status of ["approved", "failed", "cancelled"]) {
    equal(pendingBillingOrderSchema.safeParse({ ...pendingOrder, status }).success, false);
  }
  for (const timestamp of [null, "invalid", "2026-09-20", "2026-09-20T02:00:00"]) {
    equal(billingHistoryEntrySchema.safeParse({ ...approvedOrder, approved_at: timestamp }).success, false);
    equal(pendingBillingOrderSchema.safeParse({ ...pendingOrder, expires_at: timestamp }).success, false);
  }
  equal(billingOverviewResponseSchema.safeParse({
    ...emptyOverview, checkout_blocked_reason: "unknown",
  }).success, false);
  equal(billingOverviewResponseSchema.safeParse({
    ...emptyOverview, history: null,
  }).success, false, "Missing history must not silently become an empty list");
  equal(billingOverviewResponseSchema.safeParse({
    ...emptyOverview, history_has_more: "false",
  }).success, false);
}

async function checkMockOverview(): Promise<void> {
  resetMockPallyApi();
  const { profile } = await mockPallyApi.getProfile();
  const { subscription } = await mockPallyApi.getSubscription();
  const first = billingOverviewResponseSchema.parse(await mockPallyApi.getBillingOverview());
  deepEqual(first, { ...emptyOverview, subscription });
  deepEqual(await mockPallyApi.getBillingOverview(), first, "Overview reads must be deterministic");
  await mockPallyApi.createCheckout({
    product_id: "pro_monthly",
    success_url: "https://example.com/settings/plans?checkout=success",
    cancel_url: "https://example.com/settings/plans?checkout=cancel",
  }, profile.id);
  deepEqual(await mockPallyApi.getBillingOverview(), first, "Mock checkout must not invent a payment or Pro access");
  const canceled = await mockPallyApi.cancelSubscription(profile.id);
  deepEqual((await mockPallyApi.getBillingOverview()).subscription, canceled.subscription);
  await mockPallyApi.deleteAccount({ confirmation: "회원탈퇴" });
  await rejects(() => mockPallyApi.getBillingOverview(), "Deleted accounts must not access billing overview");
  resetMockPallyApi();
}

async function main(): Promise<void> {
  checkSchemas();
  await checkMockOverview();
  console.log("Billing overview contract check passed.");
}

main().catch((error: unknown) => {
  console.error("Billing overview contract check failed:", error);
  process.exit(1);
});
