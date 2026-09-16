"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { pallyApi, PallyApiError } from "@/lib/api";
import { invalidateCurrentUserConversationData } from "@/lib/api/route-data";

type ConversationNoteCardProps = {
  conversationId: string;
  feedbackHref: string;
  title: string;
};

export function ConversationNoteCard({ conversationId, feedbackHref, title }: ConversationNoteCardProps) {
  const router = useRouter();
  const [isReopening, setIsReopening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reopen = async () => {
    setIsReopening(true);
    setError(null);
    try {
      await pallyApi.reopenConversation(conversationId);
    } catch (caught) {
      if (!(caught instanceof PallyApiError && caught.code === "conversation_already_active")) {
        setError(caught instanceof Error ? caught.message : "대화를 재개하지 못했어요.");
        setIsReopening(false);
        return;
      }
    }
    await invalidateCurrentUserConversationData(conversationId).catch((caught: unknown) => {
      console.error("Conversation cache invalidation failed", caught);
    });
    window.localStorage.setItem("pally:conversationId", conversationId);
    router.push(`/home?conversation_id=${encodeURIComponent(conversationId)}`);
  };

  return (
    <article className="relative h-[134px] w-full shrink-0 rounded-[10px] bg-primary-soft">
      <span className="absolute left-2 top-0 grid size-[30px] place-items-center" aria-hidden="true">
        <img alt="" className="size-[21.17px] rotate-[35.03deg]" src="/icons/history-star.svg" />
      </span>
      <h2 className="absolute left-[23px] top-10 flex h-[30px] w-[209px] items-center truncate text-body-sb text-surface">{title}</h2>
      <img
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute left-[18px] top-[72.5px] h-[1.5px] w-[214.009px]"
        src="/icons/history-title-line.svg"
      />
      {error ? <p className="absolute bottom-1 left-[13px] text-[11px] text-red-100" role="alert">{error}</p> : null}
      <div className="absolute right-[10px] top-[84px] flex gap-4">
        <button aria-busy={isReopening} className="grid h-9 w-[83px] place-items-center rounded-full border border-surface text-button-2 text-surface disabled:opacity-60" disabled={isReopening} onClick={() => { void reopen(); }} type="button">
          대화하기
        </button>
        <Link className="grid h-9 w-[102px] place-items-center rounded-full border border-primary bg-primary text-button-2 text-white" href={feedbackHref}>피드백 보기</Link>
      </div>
    </article>
  );
}
