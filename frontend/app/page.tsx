"use client";

import { useState } from "react";

import { MobileShell } from "@/components/layout/MobileShell";
import { PallyCharacter } from "@/components/pally/PallyCharacter";
import { PageLoader } from "@/components/ui/PageLoader";
import { supabase } from "@/lib/supabase/client";

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState<"google" | "kakao" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const signIn = async (provider: "google" | "kakao") => {
    setIsLoading(provider);
    setError(null);
    const redirectTo = `${window.location.origin}/auth/callback`;
    const { error: signInError } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo,
        // Override Kakao's default email scope; this app only has profile permissions.
        ...(provider === "kakao" ? { queryParams: { scope: "profile_nickname profile_image" } } : {}),
      },
    });
    if (signInError) {
      setError(signInError.message);
      setIsLoading(null);
    }
  };

  return (
    <MobileShell>
      {isLoading ? <PageLoader message={`${isLoading === "google" ? "Google" : "카카오"} 로그인으로 연결하고 있어요`} /> : null}
      <div className="absolute left-1/2 top-[-152px] size-[450px] -translate-x-1/2 rounded-full bg-[#08bdca]" />
      <div className="absolute left-3 top-[216px] size-[138px] rounded-full bg-[#ffb84a]" />
      <PallyCharacter className="absolute left-[43px] top-[171px]" priority />

      <h1 className="absolute left-1/2 top-[479px] w-full -translate-x-1/2 text-center text-title-1 font-normal text-black">
        당신을 가장 잘 아는
        <br />
        영어 공부 파트너, <strong className="font-bold">Pally</strong>
      </h1>

      <div className="absolute left-5 right-5 top-[633px] flex flex-col gap-3">
        <button
          aria-label="Google로 시작하기"
          className="relative h-14 w-full overflow-hidden rounded-xl bg-white transition-transform active:scale-[0.99]"
          disabled={isLoading !== null}
          onClick={() => { void signIn("google"); }}
          type="button"
        >
          <span aria-hidden="true" className="absolute inset-0 rounded-xl border border-[#d9d9d9]" />
          <span className="pointer-events-none absolute left-[72.81px] top-[6.22px] h-[44.59px] w-[211.25px] overflow-hidden rounded-xl">
            <img alt="" className="absolute left-[-0.84%] top-[-6.37%] h-[112.73%] w-[101.73%] max-w-none" src="/auth/google-sign-up.png" />
          </span>
        </button>
        <button
          aria-label="카카오로 시작하기"
          className="relative h-14 w-full overflow-hidden rounded-xl bg-[#fee500] transition-transform active:scale-[0.99]"
          disabled={isLoading !== null}
          onClick={() => { void signIn("kakao"); }}
          type="button"
        >
          <span className="pointer-events-none absolute left-[84.09px] top-[4.75px] h-[45.56px] w-[201.82px] overflow-hidden">
            <img alt="" className="size-full object-cover" src="/auth/kakao-login.png" />
          </span>
        </button>
        {error ? <p className="text-center text-body-2 text-red-600" role="alert">{error}</p> : null}
      </div>
    </MobileShell>
  );
}
