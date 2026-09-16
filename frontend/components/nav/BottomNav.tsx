"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback } from "react";

import { cn } from "@/lib/utils";

const TABS = [
  { id: "home", label: "홈", href: "/home", size: 47 },
  { id: "history", label: "피드백", href: "/history/note", activePrefix: "/history", size: 40 },
  { id: "ranking", label: "업적", href: "/ranking", size: 45 },
  { id: "my", label: "마이 페이지", href: "/my", size: 40 },
] as const;

function TabIcon({ id, active, size }: { id: string; active: boolean; size: number }) {
  const icon = `url(/icons/${id}.svg)`;

  return (
    <span
      aria-hidden="true"
      className="block"
      style={{
        width: size,
        height: size,
        backgroundColor: active ? "#ffb84a" : "#ffffff",
        WebkitMaskImage: icon,
        maskImage: icon,
        WebkitMaskPosition: "center",
        maskPosition: "center",
        WebkitMaskRepeat: "no-repeat",
        maskRepeat: "no-repeat",
        WebkitMaskSize: "contain",
        maskSize: "contain",
      }}
    />
  );
}

export function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();

  const prefetchTab = useCallback((href: string) => {
    router.prefetch(href);
    void import("@/lib/api/route-data")
      .then(({ prefetchRouteData }) => prefetchRouteData(href))
      .catch((error: unknown) => {
        console.error("Tab data prefetch failed", { href, error });
      });
  }, [router]);

  return (
    <nav
      aria-label="하단 내비게이션"
      className="absolute bottom-[11px] left-[5px] z-30 h-[110px] w-[calc(100%-13px)] max-w-[389px]"
    >
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-20 rounded-[20px] bg-nav" />
      <ul className="absolute inset-x-0 bottom-0 flex h-20 items-center justify-between px-7">
        {TABS.map((tab) => {
          const activePrefix = "activePrefix" in tab ? tab.activePrefix : tab.href;
          const active = pathname === activePrefix || pathname.startsWith(`${activePrefix}/`);
          return (
            <li key={tab.id}>
              <Link
                aria-current={active ? "page" : undefined}
                aria-label={tab.label}
                className={cn(
                  "relative grid place-items-center transition-transform after:absolute after:left-1/2 after:top-1/2 after:size-12 after:-translate-x-1/2 after:-translate-y-1/2 after:content-[''] active:scale-90",
                  active && "text-primary-soft",
                )}
                href={tab.href}
                onFocus={() => prefetchTab(tab.href)}
                onPointerEnter={() => prefetchTab(tab.href)}
                onTouchStart={() => prefetchTab(tab.href)}
                style={{ width: tab.size, height: tab.size }}
              >
                <TabIcon active={active} id={tab.id} size={tab.size} />
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
