import Link from "next/link";

import { cn } from "@/lib/utils";

type PageHeaderProps = {
  title: string;
  description?: string;
  variant?: "top" | "back" | "intro";
  backHref?: string;
  showBackLink?: boolean;
  className?: string;
};

export function PageHeader({
  title,
  description,
  variant = "top",
  backHref = "/home",
  showBackLink = true,
  className,
}: PageHeaderProps) {
  if (variant === "top") {
    return (
      <header className={cn("relative h-[78px] w-[362px] overflow-hidden", className)}>
        <h1 className="text-display text-primary">{title}</h1>
      </header>
    );
  }

  if (variant === "intro") {
    return (
      <header className={cn("flex h-[128px] w-full flex-col items-start gap-3 p-5", className)}>
        <h1 className="text-title-1 text-text">{title}</h1>
        {description ? (
          <p className="break-keep whitespace-pre-line text-button-2 text-text-tertiary">{description}</p>
        ) : null}
      </header>
    );
  }

  return (
    <header className={cn("relative h-[128px] w-full", className)}>
      {showBackLink ? (
        <Link
          aria-label="뒤로 가기"
          className="absolute left-5 top-[17px] size-9 transition-opacity hover:opacity-60"
          href={backHref}
        >
          <img alt="" className="absolute left-px top-[10px] size-4" src="/icons/back.svg" />
        </Link>
      ) : null}
      <h1 className="absolute left-[61px] top-[17px] text-title-1 text-text">
        {title}
      </h1>
      {description ? (
        <p className="absolute left-5 right-5 top-[68px] break-keep whitespace-pre-line text-button-2 text-text-tertiary">
          {description}
        </p>
      ) : null}
    </header>
  );
}
