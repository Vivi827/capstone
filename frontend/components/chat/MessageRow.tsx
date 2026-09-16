type Speaker = 'you' | 'pally';

type MessageRowProps = {
  speaker: Speaker;
  transcript: string;
  state?: 'default' | 'thinking' | 'listening';
  compact?: boolean;
};

export function MessageRow({ speaker, transcript, state = 'default' }: MessageRowProps) {
  const isPally = speaker === 'pally';

  if (state === 'listening') {
    return (
      <div className="flex flex-col items-center w-full text-center">
        <p className="font-sans text-[20px] font-bold leading-7 text-accent">
          Listening...
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-1 w-full text-center">
      <p
        className={`font-sans text-[20px] font-bold leading-7 ${isPally ? 'text-accent' : 'text-primary'}`}
      >
        {isPally ? 'Pally' : 'YOU'}
      </p>
      <p
        className={`font-sans text-[16px] font-normal leading-6 ${isPally ? 'text-text' : 'text-text-tertiary'}`}
      >
        {state === 'thinking' ? 'Thinking...' : transcript}
      </p>
    </div>
  );
}
