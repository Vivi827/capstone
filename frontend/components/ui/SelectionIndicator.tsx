import { cn } from "@/lib/utils";

type SelectionIndicatorProps = {
  selected?: boolean;
  className?: string;
};

export function SelectionIndicator({ selected = false, className }: SelectionIndicatorProps) {
  return (
    <span
      aria-hidden="true"
      className={cn("block h-10 w-[39.35px]", className)}
    >
      <img alt="" className="size-full" src={selected ? "/icons/selection-selected.svg" : "/icons/selection-default.svg"} />
    </span>
  );
}
