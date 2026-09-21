"use client";

import { useEffect, useId, useRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

export const billingFocus = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#656b74]";

export function BillingButton({ className, children, secondary = false, ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { secondary?: boolean }) {
  return <button {...props} type={props.type ?? "button"} className={cn(
    "flex min-h-12 w-full items-center justify-center rounded-[10px] px-4 py-3 text-[14px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45 motion-reduce:transition-none",
    secondary ? "bg-[#f5f6f8] text-[#181a1e] hover:bg-[#eceef1]" : "bg-[#181a1e] text-white hover:bg-[#34373d]",
    billingFocus, className,
  )}>{children}</button>;
}

export function BillingFact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="flex items-start justify-between gap-5 py-2.5 text-[13px] leading-6">
    <dt className="shrink-0 text-[#656b74]">{label}</dt>
    <dd className="text-right font-medium">{children}</dd>
  </div>;
}

export function BillingChevron() {
  return <svg aria-hidden="true" className="size-4 shrink-0 text-[#8b9098]" fill="none" viewBox="0 0 16 16">
    <path d="m6 4 4 4-4 4" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
  </svg>;
}

export function BillingDialog({ title, children, onClose, busy = false, returnFocus }: {
  title: string; children: ReactNode; onClose: () => void; busy?: boolean; returnFocus?: HTMLElement | null;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef(returnFocus);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const previousFocus = opener.current ?? document.activeElement;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, []);
  return <dialog ref={ref} aria-labelledby={titleId} aria-busy={busy}
    className="fixed inset-x-0 bottom-0 top-auto m-0 mx-auto max-h-[calc(100dvh-24px)] w-full max-w-[390px] overflow-y-auto rounded-t-[20px] border-0 bg-white px-6 pb-[max(24px,env(safe-area-inset-bottom))] pt-5 text-[#181a1e] shadow-[0_-8px_40px_rgba(0,0,0,0.08)] backdrop:bg-black/30"
    onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}
    onKeyDown={(event) => {
      if (event.key !== "Tab") return;
      const targets = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
        "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
      )).filter((target) => target.getClientRects().length > 0);
      const first = targets[0];
      const last = targets[targets.length - 1];
      if (!first || !last) { event.preventDefault(); event.currentTarget.focus(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === event.currentTarget)) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === event.currentTarget)) {
        event.preventDefault(); first.focus();
      }
    }}>
    <div className="mb-6 flex items-center justify-between gap-4">
      <h2 className="text-[20px] font-semibold tracking-[-0.6px]" id={titleId}>{title}</h2>
      <button aria-label="닫기" disabled={busy} onClick={onClose} type="button"
        className={cn("-mr-3 flex size-11 shrink-0 items-center justify-center rounded-full text-[#656b74] hover:bg-[#f5f6f8] disabled:opacity-40", billingFocus)}>
        <svg aria-hidden="true" fill="none" height="20" viewBox="0 0 20 20" width="20">
          <path d="m5 5 10 10M15 5 5 15" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
        </svg>
      </button>
    </div>
    {children}
  </dialog>;
}
