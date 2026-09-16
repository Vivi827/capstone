type StreakCardProps = {
  count?: number;
};

export function StreakCard({ count = 56 }: StreakCardProps) {
  return (
    <section className="relative h-full w-full overflow-hidden rounded-[50px] bg-gradient-to-r from-primary to-primary-soft text-white">
      <strong className="absolute left-[10.33%] top-[34.55%] text-metric tabular-nums">{count}</strong>
      <span className="absolute left-[29.89%] top-[34.55%] text-title-1">Streaks!</span>
      <span className="absolute bottom-[14.55%] left-[69.57%] right-[9.24%] top-[14.55%]">
        <img alt="" className="size-full" src="/icons/streak-star.svg" />
      </span>
      <span className="absolute bottom-[16.36%] left-[83.7%] right-[5.71%] top-[48.18%]">
        <img alt="" className="size-full" src="/icons/streak-star.svg" />
      </span>
    </section>
  );
}
