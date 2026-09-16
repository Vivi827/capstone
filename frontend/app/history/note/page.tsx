"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ConversationNoteCard } from "@/components/feedback/ConversationNoteCard";
import { MobileShell } from "@/components/layout/MobileShell";
import { BottomNav } from "@/components/nav/BottomNav";
import { PageLoader } from "@/components/ui/PageLoader";
import { PallyApiError } from "@/lib/api";
import type { ConversationListItem } from "@/lib/api";
import { getCurrentUserId, loadHistoryPage } from "@/lib/api/route-data";

export default function FeedbackNotePage() {
  const router = useRouter();
  const [items, setItems] = useState<ConversationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const loadingMoreRef = useRef(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const userIdRef = useRef<string | null>(null);

  useEffect(() => {
    let active = true;

    const loadFirstPage = async () => {
      const userId = await getCurrentUserId();
      const response = await loadHistoryPage(userId);
      if (!active) return;
      userIdRef.current = userId;
      setItems(response.items);
      setNextCursor(response.next_cursor);
    };

    void loadFirstPage()
      .catch((caught: unknown) => {
        if (caught instanceof PallyApiError && caught.code === "unauthorized") {
          router.replace("/");
          return;
        }
        if (active) setError(caught instanceof Error ? caught.message : "대화 기록을 불러오지 못했어요.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [router]);

  const loadMore = useCallback(async () => {
    const userId = userIdRef.current;
    const cursor = nextCursor;
    if (!userId || !cursor || loadingMoreRef.current) return;

    loadingMoreRef.current = true;
    setIsLoadingMore(true);
    setLoadMoreError(null);
    try {
      const response = await loadHistoryPage(userId, cursor);
      setItems((current) => {
        const existingIds = new Set(current.map((item) => item.id));
        return [...current, ...response.items.filter((item) => !existingIds.has(item.id))];
      });
      setNextCursor(response.next_cursor);
    } catch (caught) {
      if (caught instanceof PallyApiError && caught.code === "unauthorized") {
        router.replace("/");
        return;
      }
      setLoadMoreError(caught instanceof Error ? caught.message : "대화 기록을 더 불러오지 못했어요.");
    } finally {
      loadingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [nextCursor, router]);

  useEffect(() => {
    if (isLoading) return;
    const root = listRef.current;
    const sentinel = sentinelRef.current;
    if (!root || !sentinel || !nextCursor || loadMoreError) return;

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) void loadMore();
    }, { root, rootMargin: "120px" });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [isLoading, loadMore, loadMoreError, nextCursor]);

  if (isLoading) {
    return (
      <MobileShell>
        <PageLoader />
      </MobileShell>
    );
  }

  return (
    <MobileShell>
      <h1 className="absolute left-5 top-[79px] text-display text-primary">History</h1>
      {!error && items.length === 0 ? (
        <p className="absolute left-5 right-5 top-1/2 -translate-y-1/2 text-center text-body text-text-tertiary">
          아직 대화 기록이 없어요!
        </p>
      ) : null}
      <div ref={listRef} className="absolute left-5 right-5 top-[180px] flex max-h-[560px] flex-col gap-3 overflow-y-auto pb-4">
        {error ? (
          <div className="flex flex-col items-center gap-2 text-center text-body text-red-600" role="alert">
            <p>{error}</p>
            <button className="rounded-full border border-red-600 px-4 py-1 text-body-2" onClick={() => window.location.reload()} type="button">다시 시도</button>
          </div>
        ) : null}
        {items.map((item) => (
          <ConversationNoteCard
            conversationId={item.id}
            feedbackHref={`/history?conversation_id=${encodeURIComponent(item.id)}`}
            key={item.id}
            title={item.title ?? item.preview ?? "Pally와 나눈 대화"}
          />
        ))}
        <div aria-hidden="true" className="h-px shrink-0" ref={sentinelRef} />
        {isLoadingMore ? <p className="py-2 text-center text-body-2 text-text-tertiary" role="status">기록을 더 불러오고 있어요</p> : null}
        {loadMoreError ? (
          <div className="flex flex-col items-center gap-2 py-2 text-center text-body-2 text-red-600" role="alert">
            <p>{loadMoreError}</p>
            <button className="rounded-full border border-red-600 px-4 py-1" onClick={() => { void loadMore(); }} type="button">다시 시도</button>
          </div>
        ) : null}
      </div>
      <BottomNav />
    </MobileShell>
  );
}
