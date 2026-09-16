"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MobileShell } from "@/components/layout/MobileShell";
import { PageLoader } from "@/components/ui/PageLoader";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { pallyApi, PallyApiError } from "@/lib/api";
import { supabase } from "@/lib/supabase/client";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const finishSignIn = async () => {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const current = await supabase.auth.getSession();
      if (current.error) throw current.error;
      if (!current.data.session && code) {
        const exchanged = await supabase.auth.exchangeCodeForSession(code);
        if (exchanged.error) throw exchanged.error;
      }

      try {
        const { profile } = await pallyApi.getProfile();
        router.replace(profile.onboarding_completed ? "/home" : "/onboarding");
      } catch (caught) {
        if (caught instanceof PallyApiError && caught.code === "profile_not_found") {
          router.replace("/onboarding");
          return;
        }
        throw caught;
      }
    };

    void finishSignIn()
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : "로그인을 완료하지 못했어요.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, [router]);

  return (
    <MobileShell>
      {isLoading ? <PageLoader message="로그인 정보를 확인하고 있어요" /> : null}
      {error ? (
        <>
          <p className="absolute inset-x-5 top-1/2 -translate-y-1/2 text-center text-body text-red-600" role="alert">{error}</p>
          <PrimaryButton className="absolute left-5 right-5 top-[calc(50%+48px)]" onClick={() => router.replace("/")}>로그인으로 돌아가기</PrimaryButton>
        </>
      ) : null}
    </MobileShell>
  );
}
