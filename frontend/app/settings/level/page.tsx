"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { NoticeDialog } from "@/components/dialogs/NoticeDialog";
import { MobileShell } from "@/components/layout/MobileShell";
import { LevelOption } from "@/components/onboarding/LevelOption";
import { PageHeader } from "@/components/ui/PageHeader";
import { PageLoader } from "@/components/ui/PageLoader";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { pallyApi, PallyApiError } from "@/lib/api";
import { cacheProfile, getCurrentUserId, loadProfile } from "@/lib/api/route-data";
import type { Level } from "@/lib/types/session";

const LEVELS = [
  { code: "A2", name: "Elementary", description: "간단한 용어를 사용해 다양한 것들을 묘사하고 간단한 표현을 이해할 수 있어요" },
  { code: "B1", name: "Intermediate", description: "여행할 때 외국어를 구사할 수 있어요. 취미와 일, 가족에 관해 대화를 나눌 수 있어요." },
  { code: "B2", name: "Upper Intermediate", description: "복잡한 주제의 대화를 이해할 수 있고 막힘 없이 원어민과 대화를 나눌 수 있어요" },
  { code: "C1", name: "Advanced", description: "사교, 학술 또는 전문적인 상황에서 외국어 능력을 구사할 수 있으며, 복잡한 대화를 따라갈 수 있어요" },
] as const;

export default function LevelSettingsPage() {
  const router = useRouter();
  const [level, setLevel] = useState<Level | null>(null);
  const [savedLevel, setSavedLevel] = useState<Level | null>(null);
  const [completedLevel, setCompletedLevel] = useState<Level | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const userIdRef = useRef<string | null>(null);
  const savingRef = useRef(false);

  useEffect(() => {
    let active = true;
    getCurrentUserId()
      .then(async (userId) => {
        userIdRef.current = userId;
        return loadProfile(userId);
      })
      .then(({ profile }) => {
        if (active) {
          setLevel(profile.english_level);
          setSavedLevel(profile.english_level);
        }
      })
      .catch((caught: unknown) => {
        if (caught instanceof PallyApiError && caught.code === "unauthorized") {
          router.replace("/");
          return;
        }
        if (active) setError(caught instanceof Error ? caught.message : "영어 레벨을 불러오지 못했어요.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router]);

  const saveLevel = async () => {
    const userId = userIdRef.current;
    if (savingRef.current || isLoading || !userId || !level || savedLevel === null || level === savedLevel) return;
    savingRef.current = true;
    setIsSaving(true);
    setError(null);
    try {
      const response = await pallyApi.updateProfile({ english_level: level });
      cacheProfile(userId, response);
      setLevel(response.profile.english_level);
      setSavedLevel(response.profile.english_level);
      setCompletedLevel(response.profile.english_level);
      savingRef.current = false;
      setIsSaving(false);
    } catch (caught) {
      console.error("English level update failed", caught);
      setError("저장하지 못했어요. 다시 시도해 주세요.");
      savingRef.current = false;
      setIsSaving(false);
    }
  };

  return (
    <MobileShell>
      {isLoading ? <PageLoader delayMs={200} message="영어 레벨을 불러오고 있어요" /> : null}
      <PageHeader backHref="/my" className="absolute left-0 top-[60px]" description="영어 레벨을 변경할 수 있어요." title="영어 레벨 변경" variant="back" />
      <fieldset aria-label="영어 레벨" className="absolute left-5 right-5 top-[220px] flex flex-col gap-3" disabled={isLoading || isSaving || savedLevel === null}>
        {LEVELS.map((item) => (
          <LevelOption code={item.code} description={item.description} key={item.code} name={item.name} onSelect={() => setLevel(item.code)} selected={level === item.code} />
        ))}
      </fieldset>
      {error ? <p className="absolute bottom-[102px] left-5 right-5 text-center text-body-2 text-red-600" role="alert">{error}</p> : null}
      <PrimaryButton aria-busy={isSaving} aria-live="polite" className="absolute bottom-[34px] left-5 w-[calc(100%-40px)]" disabled={isLoading || isSaving || savedLevel === null || level === savedLevel} onClick={() => { void saveLevel(); }}>
        {isSaving ? "저장 중..." : "변경하기"}
      </PrimaryButton>
      {completedLevel ? (
        <NoticeDialog
          body={`영어 레벨을 ${completedLevel}로 변경했어요.`}
          onConfirm={() => {
            setCompletedLevel(null);
            router.push("/my");
          }}
          title="변경 완료"
        />
      ) : null}
    </MobileShell>
  );
}
