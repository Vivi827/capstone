"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ChallengeTask } from "@/components/challenge/ChallengeTask";
import { StreakCard } from "@/components/challenge/StreakCard";
import { MobileShell } from "@/components/layout/MobileShell";
import { BottomNav } from "@/components/nav/BottomNav";
import { PageLoader } from "@/components/ui/PageLoader";
import { pallyApi, PallyApiError } from "@/lib/api";
import type { AchievementsResponse } from "@/lib/api";
import { getCurrentUserId, loadAchievements } from "@/lib/api/route-data";

export default function RankingPage() {
  const router = useRouter();
  const [data, setData] = useState<AchievementsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      const userId = await getCurrentUserId();
      void pallyApi.recordActivityEvent({
        event_id: crypto.randomUUID(),
        event_type: "achievements_opened",
        occurred_at: new Date().toISOString(),
      }).catch((caught: unknown) => {
        if (caught instanceof PallyApiError && caught.code === "unauthorized") return;
        console.error("Activity event failed", caught);
      });
      const response = await loadAchievements(userId);
      if (active) setData(response);
    };
    void load()
      .catch((caught: unknown) => {
        if (caught instanceof PallyApiError && caught.code === "unauthorized") {
          router.replace("/");
          return;
        }
        if (active) setError(caught instanceof Error ? caught.message : "Achievements를 불러오지 못했어요.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, [router]);

  if (isLoading) {
    return (
      <MobileShell>
        <PageLoader />
      </MobileShell>
    );
  }

  return (
    <MobileShell>
      <h1 className="absolute left-5 top-[62px] text-display text-primary">Achievements</h1>

      <div className="absolute left-4 right-6 top-[140px] h-[104px]">
        <StreakCard count={data?.streak_count ?? 0} />
      </div>

      <h2 className="absolute left-5 top-[280px] text-title-1 text-text">Daily Tasks</h2>
      <section aria-label="오늘의 과제" className="absolute left-5 right-5 top-[336px] flex flex-col gap-3">
        {error ? <p className="text-center text-body text-red-600" role="alert">{error}</p> : null}
        {data?.daily_tasks.map((task) => (
          <ChallengeTask
            completed={task.status === "completed"}
            description={task.description}
            key={task.id}
            title={task.title}
          />
        ))}
      </section>
      <BottomNav />
    </MobileShell>
  );
}
