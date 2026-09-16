"use client";

import { useState } from "react";

import type { Subscription, UsageResponse } from "@/lib/api";

type UsageSummaryProps = {
  subscription: Subscription | null;
  usage: UsageResponse | null;
};

function resetLabel(resetAt: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Seoul",
  }).format(new Date(resetAt));
}

export function UsageSummary({ subscription, usage }: UsageSummaryProps) {
  const [expanded, setExpanded] = useState(false);

  if (subscription?.entitled) {
    return (
      <div className="rounded-full bg-primary px-3 py-1.5 text-caption-1 text-white">
        Pro · 무제한
      </div>
    );
  }

  if (!usage) return null;

  return (
    <div className="relative">
      <button
        aria-expanded={expanded}
        className="rounded-full border border-border bg-white/90 px-3 py-1.5 text-caption-1 text-text-secondary shadow-sm"
        onClick={() => setExpanded((value) => !value)}
        type="button"
      >
        오늘 {usage.remaining_turns}/{usage.daily_limit}회 남음
      </button>
      {expanded ? (
        <section
          aria-label="오늘의 대화 사용량"
          className="absolute right-0 top-10 w-56 rounded-2xl border border-border bg-white p-4 text-body-2 text-text-secondary shadow-lg"
        >
          <div className="flex justify-between">
            <span>사용</span>
            <strong className="text-text">{usage.used_turns}회</strong>
          </div>
          <div className="mt-2 flex justify-between">
            <span>남은 대화</span>
            <strong className="text-text">{usage.remaining_turns}회</strong>
          </div>
          <div className="mt-3 border-t border-border pt-3 text-caption-1 text-text-tertiary">
            {resetLabel(usage.reset_at)} 초기화
          </div>
        </section>
      ) : null}
    </div>
  );
}
