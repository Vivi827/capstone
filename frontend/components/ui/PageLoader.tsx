"use client";

import { useEffect, useState } from "react";

type PageLoaderProps = {
  delayMs?: number;
  message?: string;
};

export function PageLoader({ delayMs = 0, message = "불러오는 중이에요" }: PageLoaderProps) {
  const [visible, setVisible] = useState(delayMs === 0);

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [delayMs]);

  if (!visible) return null;

  return (
    <div aria-live="polite" className="absolute inset-0 z-[100] flex flex-col items-center justify-center gap-5 bg-surface" role="status">
      <span aria-hidden="true" className="size-14 animate-spin rounded-full border-4 border-primary-soft border-t-primary" />
      <p className="text-body text-primary">{message}</p>
    </div>
  );
}
