import { equal, match, throws } from "node:assert/strict";

import type {
  BillingCheckoutBlockedReason,
  BillingHistoryEntry,
  BillingOverviewResponse,
  BillingProduct,
  PendingBillingOrder,
  Subscription,
} from "../lib/api/contracts";
import {
  canStartCheckout,
  checkoutBlockMessage,
  firstCharge,
  formatBillingDate,
  formatWon,
  hasBillingAccess,
  historyLabel,
  planName,
  renewalDisclosure,
  validatedCheckoutUrl,
} from "../lib/billing-view";

const now = Date.parse("2026-09-20T02:00:00Z");
const subscription: Subscription = {
  plan: "pro",
  status: "active",
  entitled: true,
  product_id: "pro_monthly",
  current_period_end: "2026-09-21T02:00:00Z",
  will_renew: true,
  entitlements: ["unlimited_turns"],
  updated_at: "2026-09-20T02:00:00Z",
};
const monthly: BillingProduct = {
  id: "pro_monthly",
  name: "Monthly",
  interval: "month",
  amount_minor: 9900,
  currency: "KRW",
  display_price: "9,900원",
  trial_days: 0,
};
const annualTrial: BillingProduct = {
  ...monthly,
  id: "pro_yearly",
  name: "Yearly",
  interval: "year",
  amount_minor: 99000,
  display_price: "99,000원",
  trial_days: 7,
};
const history: BillingHistoryEntry = {
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
  status: "uncertain",
  created_at: "2026-09-19T02:00:00Z",
  expires_at: "2026-09-19T02:30:00Z",
};
const freeOverview: BillingOverviewResponse = {
  subscription: {
    ...subscription,
    plan: "free",
    status: "none",
    entitled: false,
    product_id: null,
    current_period_end: null,
    will_renew: false,
    entitlements: [],
  },
  history: [],
  history_has_more: false,
  pending_order: null,
  checkout_blocked_reason: null,
};

function checkFormatting(): void {
  equal(formatWon(0), "0원");
  equal(formatWon(9900), "9,900원");
  equal(formatWon(99000), "99,000원");
  equal(formatBillingDate("2026-09-20T14:59:59Z"), "2026년 9월 20일");
  equal(formatBillingDate("2026-09-20T15:00:00Z"), "2026년 9월 21일");
  equal(formatBillingDate("2026-09-20T15:00:00+00:00"), "2026년 9월 21일");
  equal(planName("pro_monthly"), "월간 구독");
  equal(planName("pro_yearly"), "연간 구독");
  equal(planName(null), "Pally Pro");
  equal(planName("unknown"), "Pally Pro");
}

function checkAccessAndCheckout(): void {
  equal(hasBillingAccess(subscription, now), true);
  equal(hasBillingAccess({ ...subscription, entitled: false }, now), false);
  equal(hasBillingAccess({ ...subscription, current_period_end: null }, now), false);
  equal(hasBillingAccess({ ...subscription, current_period_end: "invalid" }, now), false);
  equal(hasBillingAccess({ ...subscription, current_period_end: new Date(now).toISOString() }, now), false);
  equal(hasBillingAccess({ ...subscription, current_period_end: new Date(now - 1).toISOString() }, now), false);
  equal(hasBillingAccess({ ...subscription, current_period_end: new Date(now + 1).toISOString() }, now), true);
  equal(hasBillingAccess({ ...subscription, will_renew: false, status: "canceled" }, now), true,
    "Turning renewal off must not remove the remaining paid period");
  equal(canStartCheckout(freeOverview, now), true);
  equal(canStartCheckout({ ...freeOverview, subscription }, now), false);
  equal(canStartCheckout({
    ...freeOverview,
    subscription: { ...subscription, current_period_end: new Date(now).toISOString(), will_renew: false },
  }, now), true, "An expired, unblocked subscription can start checkout");
  equal(canStartCheckout({ ...freeOverview, pending_order: pendingOrder }, now), false,
    "An unresolved order remains blocked even after its expiry timestamp");
  const reasons: BillingCheckoutBlockedReason[] = [
    "subscription_active", "payment_pending", "renewal_active", "deactivation_pending",
  ];
  for (const reason of reasons) {
    const blocked = { ...freeOverview, checkout_blocked_reason: reason };
    equal(canStartCheckout(blocked, now), false);
    match(checkoutBlockMessage(blocked), /[가-힣]/);
  }
  equal(checkoutBlockMessage(freeOverview), "");
  match(checkoutBlockMessage({ ...freeOverview, pending_order: pendingOrder }), /중복 결제/);
  match(checkoutBlockMessage({
    ...freeOverview,
    subscription: { ...subscription, current_period_end: new Date(Date.now() + 86400000).toISOString() },
  }), /이용 기간이 끝나면/);
}

function checkChargeCopy(): void {
  equal(firstCharge(monthly), 9900);
  equal(firstCharge(annualTrial), 0);
  equal(renewalDisclosure(monthly),
    "오늘 9,900원 결제 후 매월 자동 갱신돼요. 다음 결제 전 언제든 자동갱신을 해지할 수 있어요.");
  equal(renewalDisclosure(annualTrial),
    "7일 무료체험 후 매년 99,000원이 자동 결제돼요. 체험 종료 전 해지하면 청구되지 않아요.");
  const usedTrial = { ...annualTrial, trial_days: 0 };
  equal(firstCharge(usedTrial), 99000, "A consumed trial must not make the next checkout free");
  equal(renewalDisclosure(usedTrial),
    "오늘 99,000원 결제 후 매년 자동 갱신돼요. 다음 결제 전 언제든 자동갱신을 해지할 수 있어요.");
  match(renewalDisclosure({ ...monthly, trial_days: 7 }), /7일 무료체험 후 매월 9,900원/);
  equal(historyLabel(history), "구독 시작");
  equal(historyLabel({ ...history, kind: "renewal" }), "정기 결제");
  equal(historyLabel({ ...history, amount: 0, trial_days: 7 }), "무료체험 시작");
  equal(historyLabel({ ...history, amount: 0, trial_days: 0 }), "구독 시작");
  equal(historyLabel({ ...history, trial_days: 7 }), "구독 시작");
}

function checkCheckoutUrls(): void {
  for (const value of [
    "https://online-payment.kakaopay.com/mockup/checkout",
    "https://online-payment.kakaopay.com:443/mockup/checkout?token=test#confirm",
  ]) {
    const url = new URL(validatedCheckoutUrl(value));
    equal(url.origin, "https://online-payment.kakaopay.com");
    equal(url.pathname, "/mockup/checkout");
  }
  for (const value of [
    "not a URL",
    "/mockup/checkout",
    "//online-payment.kakaopay.com/mockup/checkout",
    "http://online-payment.kakaopay.com/mockup/checkout",
    "javascript:alert(1)",
    "https://evil.example/mockup/checkout",
    "https://online-payment.kakaopay.com.evil.example/mockup/checkout",
    "https://sub.online-payment.kakaopay.com/mockup/checkout",
    "https://online-payment.kakaopay.com:8443/mockup/checkout",
    "https://user@online-payment.kakaopay.com/mockup/checkout",
    "https://:password@online-payment.kakaopay.com/mockup/checkout",
    "https://online-payment.kakaopay.com/checkout",
    "https://online-payment.kakaopay.com/mockup",
    "https://online-payment.kakaopay.com/mockup-fake/checkout",
    "https://online-payment.kakaopay.com/mockup/../checkout",
    "https://online-payment.kakaopay.com/mockup/%2e%2e/checkout",
  ]) {
    throws(() => validatedCheckoutUrl(value), /카카오페이 결제 주소를 확인하지 못했어요/);
  }
}

checkFormatting();
checkAccessAndCheckout();
checkChargeCopy();
checkCheckoutUrls();
console.log("Billing view helper check passed.");
