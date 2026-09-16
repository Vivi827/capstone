type FeedbackCardProps = {
  original: string;
  corrected: string;
  explanation: string;
  onOpen?: () => void;
};

export function FeedbackCard({ original, corrected, explanation, onOpen }: FeedbackCardProps) {
  return (
    <button
      aria-label={`피드백 열기: ${corrected}`}
      className="block w-full shrink-0 rounded-[10px] border-0 bg-gradient-to-br from-white to-surface px-[21px] pb-6 pt-[23px] text-left shadow-[1px_3px_0_rgba(0,0,0,0.1)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/30"
      onClick={onOpen}
      type="button"
    >
      <p className="whitespace-pre-wrap break-words text-subtitle-sb text-text">“{original}”</p>
      <div className="my-[7px] h-px bg-accent" />
      <p className="whitespace-pre-wrap break-words text-subtitle text-accent">“{corrected}”</p>
      {explanation.trim() ? (
        <p className="mt-1 whitespace-pre-wrap break-words border-l-2 border-accent pl-2 text-body-2 text-text-secondary">{explanation}</p>
      ) : null}
    </button>
  );
}
