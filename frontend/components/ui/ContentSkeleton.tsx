import { cn } from "@/lib/utils";

type ContentSkeletonProps = {
  className?: string;
  rows?: number;
};

export function ContentSkeleton({ className, rows = 3 }: ContentSkeletonProps) {
  return (
    <div
      aria-label="콘텐츠를 불러오는 중"
      className={cn("flex animate-pulse flex-col gap-3", className)}
      role="status"
    >
      {Array.from({ length: rows }, (_, index) => (
        <div
          aria-hidden="true"
          className="h-[90px] w-full rounded-[10px] bg-primary-soft/35"
          key={index}
        />
      ))}
    </div>
  );
}
