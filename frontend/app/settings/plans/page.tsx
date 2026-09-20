"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";

import { MobileShell } from "@/components/layout/MobileShell";
import { PlanCard } from "@/components/profile/PlanCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { PageLoader } from "@/components/ui/PageLoader";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { pallyApi, PallyApiError } from "@/lib/api";
import type { BillingProduct, Subscription } from "@/lib/api";
import {
  getCurrentUserId,
  invalidateSubscription,
  invalidateUsage,
  loadSubscription,
} from "@/lib/api/route-data";

function productCaption(product: BillingProduct): string {
  const interval = product.interval === "year" ? "매년 자동 갱신" : "매월 자동 갱신";
  return product.trial_days > 0 ? `${product.trial_days}일 무료체험 · ${interval}` : `즉시 결제 · ${interval}`;
}

export default function PlansPage() {
  const router = useRouter();
  const [products, setProducts] = useState<BillingProduct[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [testMode, setTestMode] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);

  useEffect(() => {
    let active = true;

    const load = async () => {
      const userId = await getCurrentUserId();
      const query = new URLSearchParams(window.location.search);
      const result = z.enum(["success", "cancel", "pending"]).nullable().safeParse(query.get("checkout"));
      const checkoutResult = result.success ? result.data : null;
      const [productResponse, subscriptionResponse] = await Promise.all([
        pallyApi.getBillingProducts(),
        checkoutResult === "success" ? pallyApi.refreshSubscription() : loadSubscription(userId),
      ]);
      if (checkoutResult) {
        invalidateSubscription(userId);
        invalidateUsage(userId);
      }
      if (!active) return;
      setProducts(productResponse.products);
      setTestMode(productResponse.test_mode);
      setSubscription(subscriptionResponse.subscription);
      if (checkoutResult === "success") {
        setNotice(subscriptionResponse.subscription.entitled
          ? "Pally Pro 구독이 활성화됐어요."
          : "결제 확인 중이에요. 잠시 후 다시 확인해 주세요.");
      } else if (checkoutResult === "cancel") {
        setNotice("결제가 취소됐어요. 요금제를 다시 선택할 수 있어요.");
      } else if (checkoutResult === "pending") {
        setNotice("결제 결과를 확인 중이에요. 중복 결제하지 말고 잠시 후 다시 확인해 주세요.");
      }
    };

    void load()
      .catch((caught: unknown) => {
        if (caught instanceof PallyApiError && caught.code === "unauthorized") {
          router.replace("/");
          return;
        }
        if (active) setError(caught instanceof Error ? caught.message : "요금제를 불러오지 못했어요.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [router]);

  const visibleProducts = useMemo(() => {
    const monthly = products.find((product) => product.interval === "month");
    const yearly = products.find((product) => product.interval === "year");
    return [monthly, yearly].filter((product): product is BillingProduct => product !== undefined);
  }, [products]);
  const selectedProduct = products.find((product) => product.id === selectedProductId);

  const startCheckout = async () => {
    if (!selectedProductId || isCheckingOut) return;
    setError(null);
    setNotice(null);
    setIsCheckingOut(true);
    try {
      const returnUrl = `${window.location.origin}${window.location.pathname}`;
      const response = await pallyApi.createCheckout({
        product_id: selectedProductId,
        success_url: `${returnUrl}?checkout=success`,
        cancel_url: `${returnUrl}?checkout=cancel`,
        mobile: /Android|iPhone|iPad|iPod/i.test(navigator.userAgent),
      });
      const checkoutUrl = new URL(response.checkout.checkout_url);
      if (checkoutUrl.hostname.endsWith(".local")) {
        setNotice("현재 결제 기능이 연결되지 않아 결제창을 열 수 없어요. 카카오페이 테스트 결제 연동이 필요해요.");
        return;
      }
      window.location.assign(checkoutUrl.toString());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "결제를 시작하지 못했어요.");
    } finally {
      setIsCheckingOut(false);
    }
  };

  const stopRenewal = async () => {
    if (isCanceling || !window.confirm("자동 갱신을 해지할까요? 현재 이용 기간까지 Pro를 사용할 수 있고, 다음 결제는 진행되지 않아요.")) return;
    setIsCanceling(true);
    setError(null);
    try {
      const response = await pallyApi.cancelSubscription();
      setSubscription(response.subscription);
      const userId = await getCurrentUserId();
      invalidateSubscription(userId);
      invalidateUsage(userId);
      setNotice("자동 갱신을 해지했어요. 현재 이용 기간까지 사용할 수 있어요.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "해지하지 못했어요. 다시 시도해 주세요.");
    } finally {
      setIsCanceling(false);
    }
  };

  return (
    <MobileShell className="min-h-[950px]">
      {isLoading ? <PageLoader message="요금제를 불러오고 있어요" /> : null}
      <PageHeader
        backHref="/my"
        className="absolute left-0 top-[60px]"
        description={subscription?.entitled
          ? "현재 Pally Pro를 이용하고 있어요."
          : "Pally Pro를 구독하고 Pally와 제한 없이\n대화를 나눠보세요!"}
        title="요금제 및 결제"
        variant="back"
      />

      <h2 className="absolute left-0 right-0 top-[210px] text-center text-title-1 text-accent">Pally Pro</h2>
      <Image
        alt="Pally Pro 캐릭터"
        className="absolute left-1/2 top-[240px] size-[197px] -translate-x-1/2"
        height={197}
        priority
        src="/pally/pally-pro.svg"
        width={197}
      />
      <div className="absolute left-6 right-6 top-[440px] text-center text-caption-1 text-text-secondary">
        {testMode ? <p>테스트 결제 · 실제 금액은 청구되지 않아요.</p> : null}
        {subscription?.current_period_end ? <p>
          {subscription.status === "trialing" ? "무료체험 종료" : subscription.will_renew ? "다음 결제" : "이용 종료"}
          {" · "}{new Date(subscription.current_period_end).toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" })}
        </p> : null}
      </div>

      <div aria-label="요금제 선택" className="absolute left-[22px] right-[26px] top-[502px] flex gap-1" role="radiogroup">
        {visibleProducts.map((product) => (
          <PlanCard
            caption={subscription?.status === "trialing" && subscription.product_id === product.id
              ? "7일 무료체험 중 · 매년 자동 갱신" : productCaption(product)}
            className="flex-1"
            key={product.id}
            name={product.interval === "year" ? "연간 구독" : "월간 구독"}
            onSelect={() => {
              setSelectedProductId(product.id);
              setNotice(null);
            }}
            plan={product.interval === "year" ? "yearly" : "monthly"}
            price={product.display_price}
            selected={subscription?.entitled ? subscription.product_id === product.id : selectedProductId === product.id}
          />
        ))}
      </div>

      {selectedProduct && !subscription?.entitled ? (
        <p className="absolute left-6 right-6 top-[724px] text-center text-caption-1 text-text-secondary">
          {selectedProduct.trial_days > 0
            ? `오늘은 0원, ${selectedProduct.trial_days}일 뒤 ${selectedProduct.display_price} 결제 후 매년 자동 갱신돼요. 무료체험 종료 전 해지하면 결제되지 않아요.`
            : `오늘 ${selectedProduct.display_price} 결제 후 ${selectedProduct.interval === "year" ? "매년" : "매월"} 같은 날짜에 자동 갱신돼요. 다음 결제 전까지 해지할 수 있어요.`}
        </p>
      ) : null}
      {subscription?.will_renew ? (
        <button className="absolute left-6 right-6 top-[734px] text-body-2 text-text-secondary underline"
          disabled={isCanceling} onClick={() => { void stopRenewal(); }} type="button">
          {isCanceling ? "해지 중..." : "자동 갱신 해지"}
        </button>
      ) : null}

      {error ? <p className="absolute bottom-[102px] left-5 right-5 text-center text-body-2 text-error" role="alert">{error}</p> : null}
      {!error && notice ? <p className="absolute bottom-[102px] left-5 right-5 text-center text-body-2 text-text-tertiary" role="status">{notice}</p> : null}
      <PrimaryButton
        className="absolute bottom-[34px] left-5 w-[calc(100%-40px)]"
        disabled={selectedProductId === null || isLoading || isCheckingOut || subscription?.entitled === true}
        onClick={() => { void startCheckout(); }}
      >
        {subscription?.entitled ? "이용 중" : isCheckingOut ? "결제 준비 중..." : selectedProduct?.trial_days ? "카카오페이로 무료체험 시작" : "카카오페이로 구독하기"}
      </PrimaryButton>
    </MobileShell>
  );
}
