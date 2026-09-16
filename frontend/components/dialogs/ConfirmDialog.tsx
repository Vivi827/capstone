import { PopupActionButton } from "@/components/ui/PopupActionButton";
import { cn } from "@/lib/utils";

type ConfirmDialogProps = {
  body: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
  title: string;
  variant?: "default" | "compact";
};

export function ConfirmDialog({ body, confirmLabel, onCancel, onConfirm, title, variant = "default" }: ConfirmDialogProps) {
  const compact = variant === "compact";

  return (
    <div className="absolute inset-0 z-40 bg-black/60">
      <section
        aria-modal="true"
        className={cn(
          "absolute left-5 w-[calc(100%-40px)] rounded-3xl bg-white p-6 shadow-[0_24px_56px_rgba(28,26,23,0.14)]",
          compact ? "top-1/2 -translate-y-1/2" : "top-[332px] h-[210px]",
        )}
        role="dialog"
      >
        <h2 className={compact ? "text-title-2 text-text" : "text-title-1 text-text"}>{title}</h2>
        <p className={compact ? "mt-2 whitespace-pre-line text-caption-1 text-text-tertiary" : "mt-3 whitespace-pre-line text-[15px] leading-5 text-text-secondary"}>{body}</p>
        <div className={cn("flex justify-end gap-3", compact ? "mt-6" : "absolute bottom-6 left-6 right-6")}>
          <PopupActionButton onClick={onCancel}>돌아가기</PopupActionButton>
          <PopupActionButton onClick={onConfirm} variant="primary">{confirmLabel}</PopupActionButton>
        </div>
      </section>
    </div>
  );
}
