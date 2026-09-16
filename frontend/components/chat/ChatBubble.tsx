'use client';

import type { Message } from '@/lib/types/message';
import { cn } from '@/lib/utils';
import { MessageRow } from './MessageRow';
import { DateDivider } from './DateDivider';

const KST_DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  timeZone: 'Asia/Seoul',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

function formatConversationDate(createdAt: string): string {
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) {
    throw new Error(`Invalid message createdAt: ${createdAt}`);
  }

  const parts = KST_DATE_FORMATTER.formatToParts(date);
  const getPart = (type: 'year' | 'month' | 'day'): string => {
    const part = parts.find((item) => item.type === type);
    if (!part) throw new Error(`Missing ${type} in formatted conversation date`);
    return part.value;
  };

  return `${getPart('year')}.${getPart('month')}.${getPart('day')}`;
}

export interface ChatBubbleProps {
  messages: readonly Message[];
  expanded: boolean;
  thinking?: boolean;
  listening?: boolean;
  pendingUserTranscript?: string | null;
  onToggleExpand: () => void;
}

// Figma BoxShort (433:3266, h=450, w=402):
//   - 노란 wrapper:  inset[0 0 19.08% 0]  → top 0 ~ 80.92%  (height ~364)
//   - 흰 inner:      inset[0.01% 0 21.85% 0] → top 0 ~ 78.15% (height ~352)
//   - 보이는 노란 띠 = 흰 inner 끝 ~ 노란 wrapper 끝 = ~12.5px (78.15→80.92%)
//   - 그 아래 빈 영역 = 19.08% × 450 ≈ 86px (cream 배경)
//   - Tail (Group 4): inset[61.68% 5.47% 0 68.16%] → right=22, top=277, w≈106, h≈173
//     말풍선 꼬리 — 흰 영역 오른쪽 아래 모서리에서 노란 띠와 합쳐지는 곡선 모양
//   - Chevron (Expand_down): right=22, top=281, 40×40 (흰 영역 안)
//   - 메시지 영역: top=110, left=37, right=37, h=132 (Figma "short chat" instance)
//
// Figma BoxLong (433:3363, h=735, w=402):
//   - 노란 wrapper:  inset 0 (full)
//   - 흰 inner:      inset[0 0 2.85% 0] → top 0 ~ 97.15% (height ~714)
//   - 보이는 노란 띠 = 2.85% × 735 ≈ 21px
//   - Tail 없음
//   - Chevron (Expand_up): right=22, top=651
//   - 메시지 영역: top=24, left=16, right=16, padding 24/16, gap 12

function Chevron({ direction }: { direction: 'down' | 'up' }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn(
        'transition-transform duration-200',
        direction === 'up' ? 'rotate-180' : 'rotate-0',
      )}
    >
      <path
        d="M6 9l6 6 6-6"
        stroke="#33363f"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ChatBubble({
  messages,
  expanded,
  thinking = false,
  listening = false,
  pendingUserTranscript = null,
  onToggleExpand,
}: ChatBubbleProps) {
  if (expanded) {
    return <LongBubble messages={messages} onCollapse={onToggleExpand} pendingUserTranscript={pendingUserTranscript} thinking={thinking} />;
  }
  return (
    <ShortBubble
      messages={messages}
      thinking={thinking}
      listening={listening}
      pendingUserTranscript={pendingUserTranscript}
      onExpand={onToggleExpand}
    />
  );
}

function ShortBubble({
  messages,
  thinking,
  listening,
  pendingUserTranscript,
  onExpand,
}: {
  messages: readonly Message[];
  thinking: boolean;
  listening: boolean;
  pendingUserTranscript: string | null;
  onExpand: () => void;
}) {
  const lastPally = messages.findLast?.((m) => m.role === 'pally');
  const lastUser = messages.findLast?.((m) => m.role === 'user');

  return (
    <section
      aria-label="대화"
      className="relative w-full max-w-[402px] h-[450px] mx-auto"
    >
      {/* Order matters for z-stacking: 노란 wrapper → tail → 흰 inner.
          흰 박스가 tail 위쪽을 덮어서 진짜 말풍선 꼬리 모양으로 보이게 함. */}

      {/* 1. 노란 wrapper: bottom 19.08% 비움 (= 86px) */}
      <div
        className="absolute top-0 inset-x-0 bg-primary-soft rounded-b-[30px]"
        style={{ bottom: '19.08%' }}
        aria-hidden
      />
      {/* 2. Tail (노란 wrapper 위, 흰 박스 아래에 layered) */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/pally/chat-tail.svg"
        alt=""
        aria-hidden
        className="absolute pointer-events-none"
        style={{ right: '5.47%', top: '61.68%', width: '26.37%', height: '38.32%' }}
      />
      {/* 3. 흰 inner: bottom 21.85% 비움 (= 98px). tail의 위쪽 부분을 덮어
              말풍선 꼬리가 흰 박스에서 흘러내리는 형태로 보이게 함 */}
      <div
        className="absolute top-0 inset-x-0 bg-surface-raised rounded-b-[30px]"
        style={{ bottom: '21.85%' }}
        aria-hidden
      />

      {/* 메시지 영역 */}
      <div className="absolute top-[100px] left-[16px] right-[16px] bottom-[60px] flex flex-col gap-1 overflow-y-auto">
        {listening ? (
          // 첫 발화: Listening... 단독 / 2번째~: 마지막 Pally + Listening...
          <>
            {lastPally && (
              <MessageRow speaker="pally" transcript={lastPally.transcript} compact />
            )}
            <MessageRow speaker="pally" transcript="" state="listening" />
          </>
        ) : thinking ? (
          // Show only the current recording preview so a previous utterance cannot flash here.
          <>
            {pendingUserTranscript && <MessageRow speaker="you" transcript={pendingUserTranscript} compact />}
            <MessageRow speaker="pally" transcript="" state="thinking" />
          </>
        ) : (
          // 대화중 / idle: 마지막 유저 + 마지막 Pally
          <>
            {lastUser && <MessageRow speaker="you" transcript={lastUser.transcript} compact />}
            {lastPally && <MessageRow speaker="pally" transcript={lastPally.transcript} compact />}
          </>
        )}
      </div>

      {/* Chevron at right=22, top=281 (Figma Expand_down 40×40) */}
      <button
        type="button"
        onClick={onExpand}
        aria-label="대화 기록 펼치기"
        aria-expanded={false}
        className="absolute right-[22px] top-[281px] w-10 h-10 flex items-center justify-center rounded-md hover:bg-surface/40"
      >
        <Chevron direction="down" />
      </button>
    </section>
  );
}

function LongBubble({
  messages,
  thinking,
  pendingUserTranscript,
  onCollapse,
}: {
  messages: readonly Message[];
  thinking: boolean;
  pendingUserTranscript: string | null;
  onCollapse: () => void;
}) {
  const dateSource = messages.length > 0 ? messages[0].createdAt : new Date().toISOString();
  const conversationDate = formatConversationDate(dateSource);

  return (
    <section
      aria-label="전체 대화 기록"
      className="relative w-full max-w-[402px] h-[735px] mx-auto"
    >
      {/* 노란 wrapper: 전체 */}
      <div className="absolute inset-0 bg-primary-soft rounded-b-[30px]" aria-hidden />
      {/* 흰 inner: bottom 2.85% 비움 (~21px 노란 띠) */}
      <div
        className="absolute top-0 inset-x-0 bg-surface-raised rounded-b-[30px]"
        style={{ bottom: '2.85%' }}
        aria-hidden
      />

      {/* 메시지 리스트 — Figma 427:2804 spec: padding 24px / 16px, gap 12px */}
      <div className="absolute top-[56px] left-[16px] right-[16px] bottom-[80px] flex flex-col gap-3 overflow-y-auto">
        <DateDivider kind="date" label={conversationDate} />
        {messages.map((m, idx) => (
          <MessageRow
            key={`${m.role}-${idx}`}
            speaker={m.role === 'pally' ? 'pally' : 'you'}
            transcript={m.transcript}
          />
        ))}
        {/* Append the current utterance preview before the pending response. */}
        {thinking && (
          <>
            {pendingUserTranscript && <MessageRow speaker="you" transcript={pendingUserTranscript} />}
            <MessageRow speaker="pally" transcript="" state="thinking" />
          </>
        )}
      </div>

      {/* Chevron expand-up at right=22, top=651 */}
      <button
        type="button"
        onClick={onCollapse}
        aria-label="대화 기록 접기"
        aria-expanded={true}
        className="absolute right-[22px] top-[651px] w-10 h-10 flex items-center justify-center rounded-md hover:bg-surface/40"
      >
        <Chevron direction="up" />
      </button>
    </section>
  );
}
