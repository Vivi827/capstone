"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MobileShell } from "@/components/layout/MobileShell";
import { LevelOption } from "@/components/onboarding/LevelOption";
import { OnboardingProgress } from "@/components/onboarding/OnboardingProgress";
import { PallyCharacter } from "@/components/pally/PallyCharacter";
import { PageHeader } from "@/components/ui/PageHeader";
import { PageLoader } from "@/components/ui/PageLoader";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { TextInput } from "@/components/ui/TextInput";
import { pallyApi, PallyApiError } from "@/lib/api";
import type { Level } from "@/lib/types/session";
import { cn } from "@/lib/utils";

const LEVELS = [
  { code: "A2", name: "Elementary", description: "간단한 용어를 사용해 다양한 것들을 묘사하고 간단한 표현을 이해할 수 있어요" },
  { code: "B1", name: "Intermediate", description: "여행할 때 외국어를 구사할 수 있어요. 취미와 일, 가족에 관해 대화를 나눌 수 있어요." },
  { code: "B2", name: "Upper Intermediate", description: "복잡한 주제의 대화를 이해할 수 있고 막힘 없이 원어민과 대화를 나눌 수 있어요" },
  { code: "C1", name: "Advanced", description: "사교, 학술 또는 전문적인 상황에서 외국어 능력을 구사할 수 있으며, 복잡한 대화를 따라갈 수 있어요" },
] as const;

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [level, setLevel] = useState<Level | null>(null);
  const [name, setName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void pallyApi.getProfileAvatar()
      .then(({ avatar_url: nextAvatarUrl }) => {
        if (active) setAvatarUrl(nextAvatarUrl);
      })
      .catch((caught: unknown) => {
        console.error("Profile avatar fetch failed", caught);
        if (caught instanceof PallyApiError && caught.code === "unauthorized") {
          router.replace("/");
          return;
        }
        if (active) setError(caught instanceof Error ? caught.message : "프로필 사진을 불러오지 못했어요.");
      });
    return () => {
      active = false;
    };
  }, [router]);

  const goBack = () => setStep((value) => (value === 3 ? 2 : 1));
  const goNext = async () => {
    if (step === 3) {
      router.push("/home");
      return;
    }
    if (step === 1) {
      if (level === null) return;
      setStep(2);
      return;
    }

    if (level === null) {
      setError("영어 레벨을 선택해 주세요.");
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      await pallyApi.onboard({ display_name: name, english_level: level });
      setStep(3);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "설정을 저장하지 못했어요.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <MobileShell>
      {isSaving ? <PageLoader message="설정을 저장하고 있어요" /> : null}
      {step === 1 ? (
        <>
          <PageHeader
            className="absolute left-0 top-[60px]"
            description={"Pally와 대화 하는 용어와 문장 길이를 결정할 수\n있도록 정보를 알려주세요"}
            title="영어 레벨은?"
            variant="intro"
          />
          <div className="absolute left-5 right-5 top-[220px] flex flex-col gap-3">
            {LEVELS.map((item) => {
              const selected = level === item.code;
              return (
                <LevelOption
                  code={item.code}
                  description={item.description}
                  key={item.code}
                  name={item.name}
                  onSelect={() => setLevel(item.code)}
                  selected={selected}
                />
              );
            })}
          </div>
        </>
      ) : null}

      {step === 2 ? (
        <>
          <button aria-label="이전 단계" className="absolute left-5 top-[77px] z-10 grid size-9 place-items-center" onClick={goBack} type="button">
            <img alt="" className="absolute left-px top-[10px] size-4" src="/icons/back.svg" />
          </button>
          <PageHeader
            className="absolute left-0 top-[60px]"
            description={"Pally와 대화 하는 용어와 문장 길이를 결정할 수\n있도록 정보를 알려주세요"}
            showBackLink={false}
            title="이름 정하기"
            variant="back"
          />
          <div className="absolute left-1/2 top-[220px] size-[150px] -translate-x-1/2 overflow-hidden rounded-full bg-[#dedede]">
            <img
              alt="프로필 사진"
              className={cn("size-full object-cover", !avatarUrl && "scale-125")}
              onError={() => {
                if (avatarUrl === null) return;
                console.error("Profile avatar image failed to load");
                setAvatarUrl(null);
              }}
              referrerPolicy="no-referrer"
              src={avatarUrl ?? "/pally/pally-character.svg"}
            />
          </div>
          <TextInput
            aria-label="이름"
            className="absolute left-5 top-[460px] w-[calc(100%-40px)]"
            onChange={(event) => setName(event.target.value)}
            placeholder="이름을 입력해 주세요"
            value={name}
          />
        </>
      ) : null}

      {step === 3 ? (
        <>
          <button aria-label="이전 단계" className="absolute left-5 top-[77px] z-10 grid size-9 place-items-center" onClick={goBack} type="button">
            <img alt="" className="absolute left-px top-[10px] size-4" src="/icons/back.svg" />
          </button>
          <PageHeader
            className="absolute left-0 top-[60px]"
            description={"Pally와 함께 즐거운 공부 시간 되세요!\n이름과 영어 레벨은 설정에서 언제든 변경할 수 있어요."}
            showBackLink={false}
            title="설정 완료"
            variant="back"
          />
          <PallyCharacter className="absolute left-[29px] top-[220px]" priority />
        </>
      ) : null}

      <div className={`absolute left-[59px] ${step === 1 ? "top-[693px]" : "top-[720px]"}`}>
        <OnboardingProgress className="w-[272px] px-[112px]" step={step} />
      </div>
      {error ? <p className="absolute bottom-[102px] left-5 right-5 text-center text-body-2 text-red-600" role="alert">{error}</p> : null}
      <PrimaryButton className="absolute bottom-[34px] left-5 w-[calc(100%-40px)]" disabled={isSaving || (step === 1 && level === null) || (step === 2 && !name.trim())} onClick={goNext}>
        {isSaving ? "저장 중..." : "확인"}
      </PrimaryButton>
    </MobileShell>
  );
}
