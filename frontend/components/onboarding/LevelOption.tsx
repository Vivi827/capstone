import { SelectionIndicator } from "@/components/ui/SelectionIndicator";
import { cn } from "@/lib/utils";

type LevelOptionProps = {
  code: string;
  description: string;
  name: string;
  onSelect: () => void;
  selected?: boolean;
};

export function LevelOption({ code, description, name, onSelect, selected = false }: LevelOptionProps) {
  return (
    <button
      aria-pressed={selected}
      className={cn(
        "relative h-[90px] w-full overflow-hidden rounded-[10px] text-left transition-colors",
        selected ? "text-white" : "text-primary",
      )}
      onClick={onSelect}
      type="button"
    >
      <span
        aria-hidden="true"
        className={cn(
          "absolute inset-0 rounded-[10px] border-[3px]",
          selected ? "border-primary bg-primary" : "border-primary-soft bg-transparent",
        )}
      />
      <span aria-hidden="true" className="absolute left-[7.85px] top-[14px] grid h-[42.3px] w-[38.8px] place-items-center">
        <img
          alt=""
          className="h-[29.46px] w-[28.5px] rotate-[37.2deg] skew-x-[4.4deg]"
          src={selected ? "/icons/level-star-selected.svg" : "/icons/level-star-default.svg"}
        />
      </span>
      <p className="absolute left-[46px] right-[62px] top-[22px] truncate text-[18px] font-bold leading-[24px]">
        {code} - <span className="font-normal">{name}</span>
      </p>
      <p className={cn("absolute left-[46px] right-[58px] top-[49px] line-clamp-2 text-[11px] font-normal leading-[12px]", selected ? "text-white" : "text-text-secondary")}>
        {description}
      </p>
      <SelectionIndicator className="absolute right-5 top-1/2 h-7 w-7 -translate-y-1/2" selected={selected} />
    </button>
  );
}
