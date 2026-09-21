import type {
  BillingHistoryEntry,
  BillingOverviewResponse,
  BillingProduct,
  Subscription,
} from "@/lib/api/contracts";

const billingDateFormatter = new Intl.DateTimeFormat("ko-KR", {
  year: "numeric",
  month: "long",
  day: "numeric",
  timeZone: "Asia/Seoul",
});

export function formatWon(amount: number): string {
  return `${amount.toLocaleString("ko-KR")}원`;
}

export function formatBillingDate(value: string): string {
  return billingDateFormatter.format(new Date(value));
}

export function planName(productId: string | null): string {
  if (productId === "pro_monthly") return "월간 구독";
  if (productId === "pro_yearly") return "연간 구독";
  return "Pally Pro";
}

export function hasBillingAccess(subscription: Subscription, now = Date.now()): boolean {
  return subscription.entitled
    && subscription.current_period_end !== null
    && Date.parse(subscription.current_period_end) > now;
}

export function canStartCheckout(overview: BillingOverviewResponse, now = Date.now()): boolean {
  return !hasBillingAccess(overview.subscription, now)
    && overview.pending_order === null
    && overview.checkout_blocked_reason === null;
}

export function firstCharge(product: BillingProduct): number {
  return product.trial_days > 0 ? 0 : product.amount_minor;
}

export function renewalDisclosure(product: BillingProduct): string {
  const period = product.interval === "year" ? "매년" : "매월";
  const price = formatWon(product.amount_minor);
  if (product.trial_days > 0) {
    return `${product.trial_days}일 무료체험 후 ${period} ${price}이 자동 결제돼요. 체험 종료 전 해지하면 청구되지 않아요.`;
  }
  return `오늘 ${price} 결제 후 ${period} 자동 갱신돼요. 다음 결제 전 언제든 자동갱신을 해지할 수 있어요.`;
}

export function historyLabel(entry: BillingHistoryEntry): string {
  if (entry.amount === 0 && entry.trial_days > 0) return "무료체험 시작";
  if (entry.kind === "renewal") return "정기 결제";
  return "구독 시작";
}

export function checkoutBlockMessage(overview: BillingOverviewResponse): string {
  switch (overview.checkout_blocked_reason) {
    case "subscription_active":
      return "현재 구독을 이용 중이에요. 이용 기간이 끝나면 원하는 요금제로 다시 구독할 수 있어요.";
    case "payment_pending":
      return "결제 결과를 확인 중이에요. 중복 결제하지 말고 잠시 후 상태를 새로고침해 주세요.";
    case "renewal_active":
      return "기존 구독의 자동갱신이 켜져 있어요. 구독 상태를 확인한 뒤 다시 시도해 주세요.";
    case "deactivation_pending":
      return "자동갱신 해지를 처리 중이에요. 잠시 후 상태를 새로고침해 주세요.";
    case null:
      if (overview.pending_order !== null) {
        return "결제 결과를 확인 중이에요. 중복 결제하지 말고 잠시 후 상태를 새로고침해 주세요.";
      }
      if (hasBillingAccess(overview.subscription)) {
        return "현재 구독을 이용 중이에요. 이용 기간이 끝나면 원하는 요금제로 다시 구독할 수 있어요.";
      }
      return "";
  }
}

export function validatedCheckoutUrl(value: string): string {
  const invalidUrlMessage = "카카오페이 결제 주소를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.";
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(invalidUrlMessage);
  }
  if (
    url.protocol !== "https:"
    || url.hostname !== "online-payment.kakaopay.com"
    || (url.port !== "" && url.port !== "443")
    || url.username !== ""
    || url.password !== ""
    || !url.pathname.startsWith("/mockup/")
  ) {
    throw new Error(invalidUrlMessage);
  }
  return url.toString();
}
