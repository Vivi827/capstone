"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

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
  loadSubscription,
} from "@/lib/api/route-data";

function productCaption(product: BillingProduct): string {
  const interval = product.interval === "year" ? "1년마다 결제" : "1달마다 결제";
  return product.trial_days > 0 ? `${product.trial_days}일간 무료 체험 / ${interval}` : interval;
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

  useEffect(() => {
    let active = true;

    const load = async () => {
      const userId = await getCurrentUserId();
      const query = new URLSearchParams(window.location.search);
      const checkoutResult = query.get("checkout");
      const [productResponse, subscriptionResponse] = await Promise.all([
        pallyApi.getBillingProducts(),
        checkoutResult === "success" ? pallyApi.refreshSubscription() : loadSubscription(userId),
      ]);
      if (checkoutResult === "success") invalidateSubscription(userId);
      if (!active) return;
      setProducts(productResponse.products);
      setSubscription(subscriptionResponse.subscription);
      if (checkoutResult === "success") {
        setNotice(subscriptionResponse.subscription.entitled
          ? "Pally Pro 구독이 활성화됐어요."
          : "결제 확인 중이에요. 잠시 후 다시 확인해 주세요.");
      } else if (checkoutResult === "cancel") {
        setNotice("결제가 취소됐어요. 요금제를 다시 선택할 수 있어요.");
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
      });
      const checkoutUrl = new URL(response.checkout.checkout_url);
      if (checkoutUrl.hostname.endsWith(".local")) {
        setNotice("백엔드가 테스트 결제 모드예요. 실제 결제사는 아직 연결되지 않았어요.");
        return;
      }
      window.location.assign(checkoutUrl.toString());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "결제를 시작하지 못했어요.");
    } finally {
      setIsCheckingOut(false);
    }
  };

  return (
    <MobileShell>
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
        className="absolute left-[102px] top-[240px] size-[197px]"
        height={197}
        priority
        src="/pally/pally-pro.svg"
        width={197}
      />

      <div aria-label="요금제 선택" className="absolute left-[22px] right-[26px] top-[502px] flex gap-1" role="radiogroup">
        {visibleProducts.map((product) => (
          <PlanCard
            caption={productCaption(product)}
            className="flex-1"
            key={product.id}
            name={`${product.name} Plan`}
            onSelect={() => {
              setSelectedProductId(product.id);
              setNotice(null);
            }}
            plan={product.interval === "year" ? "yearly" : "monthly"}
            price={product.display_price}
            selected={selectedProductId === product.id}
          />
        ))}
      </div>

      {error ? <p className="absolute bottom-[102px] left-5 right-5 text-center text-body-2 text-error" role="alert">{error}</p> : null}
      {!error && notice ? <p className="absolute bottom-[102px] left-5 right-5 text-center text-body-2 text-text-tertiary" role="status">{notice}</p> : null}
      <PrimaryButton
        className="absolute bottom-[34px] left-5 w-[calc(100%-40px)]"
        disabled={selectedProductId === null || isLoading || isCheckingOut || subscription?.entitled === true}
        onClick={() => { void startCheckout(); }}
      >
        {subscription?.entitled ? "이용 중" : isCheckingOut ? "결제 준비 중..." : "확인"}
      </PrimaryButton>
    </MobileShell>
  );
}
