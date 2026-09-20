"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { MobileShell } from "@/components/layout/MobileShell";
import { BillingButton, BillingChevron, BillingDialog, BillingFact, billingFocus } from "@/components/profile/BillingUI";
import { pallyApi, PallyApiError } from "@/lib/api";
import type { BillingHistoryEntry, BillingOverviewResponse, BillingProduct } from "@/lib/api";
import { clearUserRouteData, getCurrentUserId, invalidateSubscription, invalidateUsage } from "@/lib/api/route-data";
import {
  canStartCheckout, checkoutBlockMessage, firstCharge, formatBillingDate,
  formatWon, hasBillingAccess, historyLabel, planName, renewalDisclosure, validatedCheckoutUrl,
} from "@/lib/billing-view";
import { supabase } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

type BillingData = { products: BillingProduct[]; overview: BillingOverviewResponse };
type Dialog = { kind: "checkout" } | { kind: "cancel" } | { kind: "history"; entry: BillingHistoryEntry } | null;

export default function PlansPage() {
  const router = useRouter();
  const [data, setData] = useState<BillingData | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);
  const locked = useRef(false);
  const mounted = useRef(false);
  const requestId = useRef(0);
  const userIdRef = useRef<string | null>(null);
  const authGeneration = useRef(0);
  const authInvalidated = useRef(false);
  const departingForCheckout = useRef(false);
  const dialogOpener = useRef<HTMLElement | null>(null);

  const clearBillingSession = useCallback(() => {
    authGeneration.current += 1;
    authInvalidated.current = true;
    requestId.current += 1;
    if (userIdRef.current) clearUserRouteData(userIdRef.current);
    userIdRef.current = null;
    locked.current = false;
    departingForCheckout.current = false;
    dialogOpener.current = null;
    setData(null);
    setSelectedId(null);
    setDialog(null);
    setDialogError(null);
    setNotice(null);
    setError(null);
    setBusy(false);
    setLoading(false);
    router.replace("/");
  }, [router]);

  const isCurrentSession = useCallback((generation: number) => (
    mounted.current && !authInvalidated.current && generation === authGeneration.current
  ), []);

  useEffect(() => {
    const { data: listener } = supabase.auth.onAuthStateChange((event, session) => {
      if (authInvalidated.current) return;
      const nextUserId = session?.user.id ?? null;
      if (event === "SIGNED_OUT" || (userIdRef.current !== null && nextUserId !== userIdRef.current)) {
        clearBillingSession();
        return;
      }
      userIdRef.current = nextUserId;
    });
    return () => listener.subscription.unsubscribe();
  }, [clearBillingSession]);

  const handleError = useCallback((caught: unknown, inDialog = false) => {
    if (!mounted.current || authInvalidated.current) return;
    if (caught instanceof PallyApiError && caught.code === "unauthorized") {
      clearBillingSession();
      return;
    }
    const message = caught instanceof Error ? caught.message : "결제 정보를 불러오지 못했어요. 다시 시도해 주세요.";
    if (mounted.current) (inDialog ? setDialogError : setError)(message);
  }, [clearBillingSession]);

  const loadData = useCallback(async (reconcile = false): Promise<BillingData | null> => {
    const generation = authGeneration.current;
    const id = ++requestId.current;
    if (!isCurrentSession(generation)) return null;
    const userId = await getCurrentUserId();
    if (!isCurrentSession(generation) || id !== requestId.current) return null;
    if (userIdRef.current !== null && userIdRef.current !== userId) {
      clearBillingSession();
      return null;
    }
    userIdRef.current = userId;
    if (reconcile) await pallyApi.refreshSubscription(userId);
    if (!isCurrentSession(generation) || id !== requestId.current) return null;
    const [catalog, overview] = await Promise.all([pallyApi.getBillingProducts(), pallyApi.getBillingOverview()]);
    if (!isCurrentSession(generation) || id !== requestId.current || userIdRef.current !== userId) return null;
    const next = { products: catalog.products, overview };
    invalidateSubscription(userId);
    invalidateUsage(userId);
    if (mounted.current && id === requestId.current) {
      setData(next);
      setSelectedId((current) => catalog.products.some((product) => product.id === current)
        ? current : (catalog.products.find((product) => product.interval === "year")?.id ?? catalog.products[0]?.id ?? null));
    }
    return next;
  }, [clearBillingSession, isCurrentSession]);

  useEffect(() => {
    let active = true;
    mounted.current = true;
    const generation = authGeneration.current;
    const checkout = new URLSearchParams(window.location.search).get("checkout");
    void loadData(checkout === "success" || checkout === "pending")
      .then((next) => {
        if (!active || !next || !isCurrentSession(generation)) return;
        if (checkout === "success" && hasBillingAccess(next.overview.subscription)) {
          setNotice("Pally Pro를 이용할 수 있어요.");
        } else if (checkout === "cancel") {
          setNotice("결제창을 닫았어요. 아래에서 현재 결제 상태를 확인해 주세요.");
        }
        if (["success", "pending", "cancel"].includes(checkout ?? "")) {
          window.history.replaceState(window.history.state, "", window.location.pathname);
        }
      })
      .catch((caught: unknown) => { if (active && isCurrentSession(generation)) handleError(caught); })
      .finally(() => { if (active && isCurrentSession(generation)) setLoading(false); });
    return () => { active = false; mounted.current = false; requestId.current += 1; };
  }, [handleError, isCurrentSession, loadData]);

  const refresh = useCallback(async (reconcile = true) => {
    const generation = authGeneration.current;
    if (locked.current || !isCurrentSession(generation)) return;
    locked.current = true;
    setBusy(true);
    setError(null);
    setNotice(null);
    try { await loadData(reconcile); }
    catch (caught) { if (isCurrentSession(generation)) handleError(caught); }
    finally { if (isCurrentSession(generation)) { locked.current = false; setBusy(false); setLoading(false); } }
  }, [handleError, isCurrentSession, loadData]);

  useEffect(() => {
    const restore = (event: PageTransitionEvent) => {
      if (!event.persisted && !departingForCheckout.current) return;
      departingForCheckout.current = false;
      locked.current = false;
      setBusy(false);
      setDialog(null);
      setDialogError(null);
      void refresh(false);
    };
    window.addEventListener("pageshow", restore);
    return () => window.removeEventListener("pageshow", restore);
  }, [refresh]);

  useEffect(() => {
    const end = data?.overview.subscription.current_period_end;
    if (!end || !data.overview.subscription.entitled) return;
    const delay = new Date(end).getTime() - Date.now();
    if (delay <= 0 || delay > 2_147_000_000) return;
    const timer = window.setTimeout(() => { void refresh(false); }, delay + 100);
    return () => window.clearTimeout(timer);
  }, [data, refresh]);

  const closeDialog = () => { if (!locked.current) { setDialog(null); setDialogError(null); } };
  const selected = data?.products.find((product) => product.id === selectedId);
  const overview = data?.overview;
  const subscription = overview?.subscription;
  const entitled = subscription ? hasBillingAccess(subscription) : false;
  const currentProduct = data?.products.find((product) => product.id === subscription?.product_id);
  const pending = overview?.pending_order;
  const purchasable = overview ? canStartCheckout(overview) : false;

  const openCheckout = async () => {
    const generation = authGeneration.current;
    if (locked.current || !selected || !purchasable || !isCurrentSession(generation)) return;
    locked.current = true;
    setBusy(true);
    setDialogError(null);
    setError(null);
    setDialog({ kind: "checkout" });
    try {
      const next = await loadData();
      if (!next || !isCurrentSession(generation)) return;
      if (!canStartCheckout(next.overview)) {
        setDialog(null);
        setError(checkoutBlockMessage(next.overview));
      }
    } catch (caught) { if (isCurrentSession(generation)) handleError(caught, true); }
    finally { if (isCurrentSession(generation)) { locked.current = false; setBusy(false); } }
  };

  const startCheckout = async () => {
    const generation = authGeneration.current;
    if (locked.current || !selected || !purchasable || dialogError || !isCurrentSession(generation)) return;
    locked.current = true;
    setBusy(true);
    setDialogError(null);
    try {
      const userId = await getCurrentUserId();
      if (!isCurrentSession(generation)) return;
      if (userId !== userIdRef.current) { clearBillingSession(); return; }
      const returnUrl = `${window.location.origin}${window.location.pathname}`;
      const response = await pallyApi.createCheckout({
        product_id: selected.id,
        success_url: `${returnUrl}?checkout=success`,
        cancel_url: `${returnUrl}?checkout=cancel`,
        mobile: /Android|iPhone|iPad|iPod/i.test(navigator.userAgent),
      }, userId);
      if (!isCurrentSession(generation)) return;
      if (response.checkout.product_id !== selected.id) throw new Error("선택한 요금제와 결제 정보가 달라요. 다시 시도해 주세요.");
      const url = validatedCheckoutUrl(response.checkout.checkout_url);
      departingForCheckout.current = true;
      window.location.assign(url);
      // Keep the lock until navigation finishes so another click cannot create an order.
    } catch (caught) {
      if (!isCurrentSession(generation)) return;
      handleError(caught, true);
      locked.current = false;
      if (mounted.current) setBusy(false);
    }
  };

  const stopRenewal = async () => {
    const generation = authGeneration.current;
    if (locked.current || !subscription?.will_renew || !isCurrentSession(generation)) return;
    locked.current = true;
    setBusy(true);
    setDialogError(null);
    try {
      const userId = await getCurrentUserId();
      if (!isCurrentSession(generation)) return;
      if (userId !== userIdRef.current) { clearBillingSession(); return; }
      const response = await pallyApi.cancelSubscription(userId);
      if (!isCurrentSession(generation)) return;
      if (userIdRef.current) {
        invalidateSubscription(userIdRef.current);
        invalidateUsage(userIdRef.current);
      }
      setData((current) => current ? { ...current, overview: { ...current.overview, subscription: response.subscription } } : null);
      setDialog(null);
      setNotice("자동갱신을 해지했어요. 남은 이용 기간은 그대로 유지돼요.");
      try { await loadData(); }
      catch (caught) { if (isCurrentSession(generation)) handleError(caught); }
    } catch (caught) { if (isCurrentSession(generation)) handleError(caught, true); }
    finally { if (isCurrentSession(generation)) { locked.current = false; setBusy(false); } }
  };

  return <div className="min-h-dvh bg-white">
    <MobileShell className="min-h-dvh max-w-[390px] bg-white pb-[max(32px,env(safe-area-inset-bottom))] text-[#181a1e]">
      <header className="flex h-[76px] items-center gap-2 px-3 pt-2">
        <Link aria-label="마이페이지로 돌아가기" className={cn("flex size-11 items-center justify-center rounded-full hover:bg-[#f5f6f8]", billingFocus)} href="/my">
          <Image alt="" height={20} src="/icons/back.svg" width={20} />
        </Link>
        <span className="text-[15px] font-medium tracking-[-0.3px]">요금제 및 결제</span>
      </header>
      <div className="px-6 pt-6">
        {loading ? <div aria-busy="true" className="py-20 text-center text-[13px] text-[#656b74]" role="status">결제 정보를 불러오고 있어요.</div> : null}
        {notice ? <p className="mb-6 rounded-lg bg-[#f5f6f8] px-4 py-3 text-[13px] leading-6 text-[#656b74]" role="status">{notice}</p> : null}
        {error ? <div className="mb-6 rounded-lg border border-[#eceef1] p-4">
          <p className="text-[13px] leading-6 text-[#a83232]" role="alert">{error}</p>
          <button className={cn("mt-2 min-h-11 text-[13px] font-medium underline underline-offset-4", billingFocus)} disabled={busy} onClick={() => { void refresh(false); }} type="button">{busy ? "확인 중…" : "다시 확인"}</button>
        </div> : null}

        {!loading && data && overview && subscription ? <>
          {pending ? <section aria-labelledby="pending-title">
            <div className="mb-5 flex size-9 items-center justify-center rounded-full bg-[#f5f6f8] text-[#656b74]">
              <svg aria-hidden="true" fill="none" height="19" viewBox="0 0 20 20" width="19"><circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.4" /><path d="M10 6v4l2.5 1.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.4" /></svg>
            </div>
            <h1 className="text-[25px] font-semibold tracking-[-1px]" id="pending-title">결제 확인 중</h1>
            <p className="mt-3 text-[13px] leading-[1.9] text-[#656b74]">{pending.status === "ready" || pending.status === "preparing"
              ? "진행 중인 결제가 있어요. 열려 있는 카카오페이 결제창을 확인해 주세요. 결제하지 않았다면 대기 시간이 지난 뒤 다시 선택할 수 있어요."
              : pending.status === "uncertain"
                ? "결제 결과를 확인하지 못했어요. 중복 결제하지 말고 상태를 다시 확인해 주세요. 이 상태가 계속되면 운영팀의 확인이 필요해요."
                : <>결제가 완료됐는지 확인하고 있어요.<br />중복 결제하지 말고 잠시 후 다시 확인해 주세요.</>}</p>
            <dl className="mb-6 mt-7 border-y border-[#eceef1] py-3">
              <BillingFact label="요금제">{planName(pending.product_id)}</BillingFact>
              <BillingFact label="결제 금액">{formatWon(pending.amount)}</BillingFact>
              <BillingFact label="현재 이용 상태">{entitled ? "Pally Pro" : "Free"}</BillingFact>
              {entitled && subscription.current_period_end ? <BillingFact label="이용 가능일">{formatBillingDate(subscription.current_period_end)}까지</BillingFact> : null}
            </dl>
            <BillingButton className="w-auto min-w-[142px]" disabled={busy} onClick={() => { void refresh(); }} secondary>{busy ? "확인 중…" : "상태 새로고침"}</BillingButton>
          </section> : entitled ? <section aria-labelledby="subscription-title">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[12px] font-medium tracking-[1.5px] text-[#656b74]">PALLY <span className="text-[#dd7410]">PRO</span></p>
              <span className="flex items-center gap-1.5 rounded-full bg-[#f5f6f8] px-2.5 py-1 text-[11px] font-medium text-[#656b74]">
                <span className={cn("size-1.5 rounded-full", subscription.will_renew ? "bg-[#fe9012]" : "bg-[#8b9098]")} />
                {subscription.will_renew ? (subscription.status === "trialing" ? "무료체험 중" : "이용 중") : "자동갱신 꺼짐"}
              </span>
            </div>
            <h1 className="mt-4 text-[27px] font-semibold tracking-[-1px]" id="subscription-title">Pally Pro</h1>
            <p className="mt-2 text-[13px] leading-6 text-[#656b74]">{subscription.will_renew ? "Pally와 더 자유롭게 대화해 보세요." : "남은 기간 동안 Pro를 그대로 이용하세요."}</p>
            <div className="mt-8 border-b border-[#eceef1] pb-7">
              <p className="text-[12px] text-[#656b74]">{subscription.will_renew ? (subscription.status === "trialing" ? "첫 결제일" : "다음 결제일") : "이용 종료일"}</p>
              <p className="mt-2 text-[23px] font-medium tracking-[-0.8px]">{subscription.current_period_end ? formatBillingDate(subscription.current_period_end) : "확인 필요"}</p>
              {!subscription.will_renew ? <p className="mt-2 text-[12px] leading-5 text-[#656b74]">추가 결제 없이, 위 날짜까지 Pro를 이용할 수 있어요.</p> : null}
            </div>
            <dl className="py-4">
              <BillingFact label="요금제">{planName(subscription.product_id)}</BillingFact>
              {currentProduct ? <BillingFact label="구독 금액">{formatWon(currentProduct.amount_minor)} / {currentProduct.interval === "year" ? "년" : "월"}</BillingFact> : null}
              <BillingFact label="결제 수단">카카오페이</BillingFact>
            </dl>
            {!subscription.will_renew ? <p className="text-[12px] leading-5 text-[#656b74]">이용 기간이 끝나면 원하는 요금제로 다시 구독할 수 있어요.</p> : null}
          </section> : purchasable ? <section aria-labelledby="plans-title">
            <p className="text-[12px] font-medium tracking-[1.5px] text-[#656b74]">PALLY <span className="text-[#dd7410]">PRO</span></p>
            <h1 className="mt-4 text-[27px] font-semibold tracking-[-1px]" id="plans-title">Pally와 더 자유롭게</h1>
            <p className="mt-3 text-[13px] leading-[1.9] text-[#656b74]">나에게 맞는 요금제를 선택하고<br />Pally와의 대화를 이어가세요.</p>
            <fieldset className="mt-8 space-y-3">
              <legend className="mb-3 text-[13px] font-medium">요금제 선택</legend>
              {[...data.products].sort((a, b) => (a.interval === "month" ? 0 : 1) - (b.interval === "month" ? 0 : 1)).map((product) => <label
                className={cn("relative flex min-h-[86px] cursor-pointer items-center gap-3 rounded-[10px] border px-4 py-4 transition-colors focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[#656b74] motion-reduce:transition-none",
                  selectedId === product.id ? "border-[#c6cbd2] bg-[#f5f6f8]" : "border-[#eceef1] bg-white hover:border-[#c6cbd2]")}
                key={product.id}>
                <input checked={selectedId === product.id} className="peer sr-only" disabled={busy} name="billing-plan" onChange={() => { setSelectedId(product.id); setError(null); }} type="radio" value={product.id} />
                <span aria-hidden="true" className={cn("flex size-[18px] shrink-0 items-center justify-center rounded-full border", selectedId === product.id ? "border-[#181a1e] bg-[#181a1e]" : "border-[#c6cbd2]")}>
                  {selectedId === product.id ? <span className="size-1.5 rounded-full bg-white" /> : null}
                </span>
                <span className="min-w-0 flex-1"><span className="block text-[14px] font-medium">{planName(product.id)}</span>
                  <span className="mt-1 block text-[12px] text-[#656b74]">{product.trial_days > 0 ? `${product.trial_days}일 무료체험` : product.interval === "year" ? "매년 자동갱신" : "매월 자동갱신"}</span>
                </span>
                <span className="shrink-0 text-right"><span className="block text-[18px] font-medium tracking-[-0.5px]">{formatWon(product.amount_minor)}</span><span className="text-[12px] text-[#656b74]">/ {product.interval === "year" ? "년" : "월"}</span></span>
              </label>)}
            </fieldset>
            {data.products.length === 0 ? <p className="mt-4 text-[13px] text-[#656b74]" role="status">현재 선택할 수 있는 요금제가 없어요.</p> : null}
            <BillingButton className="mt-6" disabled={!selected || busy} onClick={(event) => { dialogOpener.current = event.currentTarget; void openCheckout(); }}>{busy ? "확인 중…" : "계속하기"}</BillingButton>
            {selected ? <p className="mt-3 text-center text-[12px] leading-[1.8] text-[#656b74]">{renewalDisclosure(selected)}</p> : null}
          </section> : <section aria-labelledby="blocked-title">
            <h1 className="text-[25px] font-semibold tracking-[-1px]" id="blocked-title">구독 상태 확인</h1>
            <p className="mb-6 mt-3 text-[13px] leading-6 text-[#656b74]">{checkoutBlockMessage(overview)}</p>
            <BillingButton disabled={busy} onClick={() => { void refresh(); }} secondary>{busy ? "확인 중…" : "상태 새로고침"}</BillingButton>
          </section>}

          <section aria-labelledby="history-title" className="mt-9 border-t border-[#eceef1] pt-6">
            <div className="mb-2 flex items-center justify-between gap-3">
              <h2 className="text-[15px] font-semibold" id="history-title">결제 내역</h2>
              {overview.history_has_more ? <span className="text-[12px] text-[#656b74]">최근 50건</span> : null}
            </div>
            {overview.history.length === 0 ? <p className="py-5 text-[13px] text-[#656b74]">아직 결제 내역이 없어요.</p> : <ul className="divide-y divide-[#eceef1]">
              {overview.history.map((entry) => <li key={entry.id}>
                <button className={cn("flex min-h-[76px] w-full items-center gap-3 rounded px-0 py-4 text-left", billingFocus)} onClick={(event) => { dialogOpener.current = event.currentTarget; setDialogError(null); setDialog({ kind: "history", entry }); }} type="button">
                  <span className="min-w-0 flex-1"><span className="block text-[13px] font-medium">{planName(entry.product_id)}</span><span className="mt-1 block text-[12px] text-[#656b74]">{formatBillingDate(entry.approved_at)}</span></span>
                  <span className="text-right"><span className="block text-[14px] font-medium tabular-nums">{formatWon(entry.amount)}</span><span className="mt-1 block text-[12px] text-[#656b74]">{entry.amount === 0 ? "청구 없음" : "결제 완료"}</span></span>
                  <BillingChevron />
                </button>
              </li>)}
            </ul>}
          </section>
          {entitled && subscription.will_renew ? <div className="mt-5 border-t border-[#eceef1] pt-3">
            <button className={cn("min-h-11 text-[12px] text-[#656b74] underline underline-offset-4", billingFocus)} disabled={busy || Boolean(pending)} onClick={(event) => { dialogOpener.current = event.currentTarget; setDialogError(null); setDialog({ kind: "cancel" }); }} type="button">자동갱신 해지</button>
            <p className="mt-1 text-[12px] leading-5 text-[#656b74]">다른 요금제는 자동갱신 해지 후, 이용 기간이 끝나면 선택할 수 있어요.</p>
          </div> : null}
        </> : null}
      </div>

      {dialog ? <BillingDialog busy={busy} onClose={closeDialog} returnFocus={dialogOpener.current} title={dialog.kind === "checkout" ? "구독 시작하기" : dialog.kind === "cancel" ? "자동갱신을 해지할까요?" : "결제 상세"}>
        {dialog.kind === "checkout" && selected ? <>
          <p className="text-[13px] text-[#656b74]">Pally Pro · {planName(selected.id)}</p>
          <div className="mb-4 mt-6 flex items-end justify-between border-b border-[#eceef1] pb-6"><span className="text-[13px] text-[#656b74]">오늘 결제할 금액</span><strong className="text-[28px] font-semibold tracking-[-1px]">{formatWon(firstCharge(selected))}</strong></div>
          <dl>
            <BillingFact label="결제 수단">카카오페이</BillingFact>
            <BillingFact label="정기 결제">{formatWon(selected.amount_minor)} / {selected.interval === "year" ? "년" : "월"}</BillingFact>
            {selected.trial_days > 0 ? <BillingFact label="첫 결제">체험 시작 {selected.trial_days}일 후</BillingFact> : null}
          </dl>
          <p className="my-5 text-[12px] leading-[1.9] text-[#656b74]">{renewalDisclosure(selected)}</p>
          {dialogError ? <p className="mb-4 text-[13px] leading-6 text-[#a83232]" role="alert">{dialogError}<br />창을 닫고 다시 시도해 주세요.</p> : null}
          <BillingButton disabled={busy || !purchasable || Boolean(dialogError)} onClick={() => { void startCheckout(); }}>{busy ? "결제 준비 중…" : selected.trial_days > 0 ? "카카오페이로 무료체험 시작" : "카카오페이로 결제하기"}</BillingButton>
        </> : null}
        {dialog.kind === "cancel" ? <>
          <p className="text-[13px] leading-[1.9] text-[#656b74]">다음 자동 결제만 중단돼요.<br />{subscription?.current_period_end ? `${formatBillingDate(subscription.current_period_end)}까지 Pro를 그대로 이용할 수 있어요.` : "현재 이용 기간은 그대로 유지돼요."}</p>
          <p className="mb-7 mt-3 text-[12px] leading-[1.9] text-[#656b74]">이용 기간이 끝나면 원하는 요금제로 다시 구독할 수 있어요.</p>
          {dialogError ? <p className="mb-4 text-[13px] leading-6 text-[#a83232]" role="alert">{dialogError}</p> : null}
          <BillingButton disabled={busy} onClick={() => { void stopRenewal(); }}>{busy ? "해지 중…" : "자동갱신 해지하기"}</BillingButton>
          <BillingButton className="mt-2" disabled={busy} onClick={closeDialog} secondary>계속 이용하기</BillingButton>
        </> : null}
        {dialog.kind === "history" ? <>
          <p className="text-[13px] text-[#656b74]">{historyLabel(dialog.entry)} · {planName(dialog.entry.product_id)}</p>
          <p className="mb-6 mt-3 text-[30px] font-semibold tracking-[-1px]">{formatWon(dialog.entry.amount)}</p>
          <dl className="mb-6 border-y border-[#eceef1] py-3">
            <BillingFact label="결제일">{formatBillingDate(dialog.entry.approved_at)}</BillingFact>
            <BillingFact label="결제 수단">카카오페이</BillingFact>
            <BillingFact label="상태">{dialog.entry.amount === 0 ? "청구 없음" : "결제 완료"}</BillingFact>
          </dl>
          <BillingButton onClick={closeDialog} secondary>확인</BillingButton>
        </> : null}
      </BillingDialog> : null}
    </MobileShell>
  </div>;
}
