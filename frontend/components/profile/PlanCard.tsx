import { cn } from "@/lib/utils";

type PlanCardProps = {
  caption: string;
  className?: string;
  name: string;
  onSelect: () => void;
  plan: "monthly" | "yearly";
  price: string;
  selected: boolean;
};

export function PlanCard({ caption, className, name, onSelect, plan, price, selected }: PlanCardProps) {
  const yearly = plan === "yearly";

  return (
    <button
      aria-checked={selected}
      className={cn(
        "relative flex h-[200px] min-w-0 flex-col items-start gap-3 rounded-[20px] border-0 pb-7 pt-[35px] text-left transition-transform duration-150 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/40 active:scale-[0.99]",
        yearly
          ? "bg-gradient-to-b from-primary-soft to-primary px-[13px]"
          : "bg-gradient-to-b from-[#ffe3b8] to-primary-soft pl-3 pr-[15px]",
        selected && "shadow-[inset_0_0_0_2px_#c65f00]",
        className,
      )}
      onClick={onSelect}
      role="radio"
      type="button"
    >
      <p className={`whitespace-nowrap text-[36px] font-black leading-[44px] ${yearly ? "text-white" : "text-primary"}`}>
        {price}
      </p>
      <h2 className="whitespace-nowrap text-title-2 text-white">{name}</h2>
      <div className="h-px w-full bg-white" />
      <p className="whitespace-nowrap text-caption-2 text-white">{caption}</p>
    </button>
  );
}
