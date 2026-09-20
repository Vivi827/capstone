import { deepEqual, equal, rejects } from "node:assert/strict";
import { randomUUID } from "node:crypto";
import type { Session } from "@supabase/supabase-js";

import { PallyApiError } from "../lib/api/contracts";
import { mockPallyApi, resetMockPallyApi } from "../lib/api/mock-client";

const checkoutInput = {
  product_id: "pro_monthly",
  success_url: "https://fixture.invalid/settings/plans?checkout=success",
  cancel_url: "https://fixture.invalid/settings/plans?checkout=cancel",
};

function fixtureSession(userId: string): Session {
  return {
    access_token: `fixture-access-${userId}`,
    refresh_token: `fixture-refresh-${userId}`,
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    token_type: "bearer",
    user: {
      id: userId,
      aud: "authenticated",
      role: "authenticated",
      app_metadata: {},
      user_metadata: {},
      created_at: "2026-09-20T00:00:00Z",
    },
  };
}

function isUnauthorized(error: unknown): boolean {
  return error instanceof PallyApiError && error.status === 401 && error.code === "unauthorized";
}

async function checkHttpBinding(): Promise<void> {
  const environmentNames = ["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "NEXT_PUBLIC_BACKEND_URL"] as const;
  const previousEnvironment = environmentNames.map((name) => [name, process.env[name]] as const);
  const originalFetch = globalThis.fetch;
  const calls: { path: string; method: string | undefined; authorization: string | null; body: BodyInit | null | undefined }[] = [];
  let responsePayload: unknown;

  // All values and requests are fixtures. No local or deployed backend is contacted.
  process.env.NEXT_PUBLIC_SUPABASE_URL = "https://fixture.supabase.invalid";
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "fixture-public-anon-key";
  process.env.NEXT_PUBLIC_BACKEND_URL = "https://fixture-backend.invalid";
  globalThis.fetch = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : input.toString());
    equal(url.origin, "https://fixture-backend.invalid", "No external network request is allowed");
    calls.push({ path: url.pathname, method: init?.method, authorization: new Headers(init?.headers).get("Authorization"), body: init?.body });
    return new Response(JSON.stringify(responsePayload), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  try {
    const { httpPallyApi } = await import("../lib/api/http-client");
    const { supabase } = await import("../lib/supabase/client");
    const originalGetSession = supabase.auth.getSession;
    const userA = randomUUID();
    const userB = randomUUID();
    const sessionA = fixtureSession(userA);
    const subscriptionResponse = {
      subscription: { plan: "free", status: "none", entitled: false, product_id: null, current_period_end: null, will_renew: false, entitlements: [], updated_at: null },
    };
    const operations = [
      {
        name: "checkout",
        path: "/api/billing/checkout",
        invoke: (userId: string) => httpPallyApi.createCheckout(checkoutInput, userId),
        response: { checkout: { product_id: "pro_monthly", checkout_url: "https://online-payment.kakaopay.com/mockup/fixture", expires_at: "2026-09-20T00:30:00Z" } },
      },
      { name: "cancel", path: "/api/subscription/cancel", invoke: (userId: string) => httpPallyApi.cancelSubscription(userId), response: subscriptionResponse },
      { name: "refresh", path: "/api/subscription/refresh", invoke: (userId: string) => httpPallyApi.refreshSubscription(userId), response: subscriptionResponse },
    ];
    try {
      for (const operation of operations) {
        calls.length = 0;
        let finishSessionRead: ((value: { data: { session: Session }; error: null }) => void) | undefined;
        supabase.auth.getSession = () => new Promise((resolve) => { finishSessionRead = resolve; });
        const pendingMutation = operation.invoke(userA);
        if (!finishSessionRead) throw new Error(`${operation.name}: the token session read must be awaiting resolution`);
        // The page bound its action to A, but getSession completes after the browser switched to B.
        finishSessionRead({ data: { session: fixtureSession(userB) }, error: null });
        await rejects(pendingMutation, isUnauthorized, `${operation.name}: reject a changed user before fetch`);
        equal(calls.length, 0, `${operation.name}: session switching must issue zero fetches`);

        supabase.auth.getSession = async () => ({ data: { session: null }, error: null });
        await rejects(operation.invoke(userA), isUnauthorized, `${operation.name}: signed-out sessions cannot mutate billing`);
        equal(calls.length, 0);

        const refreshedSession = { ...sessionA, access_token: "fixture-user-a-refreshed" };
        supabase.auth.getSession = async () => ({ data: { session: refreshedSession }, error: null });
        await rejects(operation.invoke(""), isUnauthorized, `${operation.name}: an empty account binding fails closed`);
        equal(calls.length, 0);

        responsePayload = operation.response;
        await operation.invoke(userA);
        equal(calls.length, 1, `${operation.name}: the same user may submit exactly once`);
        equal(calls[0].path, operation.path);
        equal(calls[0].method, "POST");
        equal(calls[0].authorization, "Bearer fixture-user-a-refreshed", "The checked session supplies the actual bearer token");
        if (operation.name === "checkout") deepEqual(JSON.parse(String(calls[0].body)), checkoutInput, "Account binding does not alter the backend wire payload");
      }
    } finally {
      supabase.auth.getSession = originalGetSession;
      await supabase.auth.stopAutoRefresh();
    }
  } finally {
    globalThis.fetch = originalFetch;
    for (const [name, value] of previousEnvironment) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }
}

async function checkMockBinding(): Promise<void> {
  resetMockPallyApi();
  const { profile } = await mockPallyApi.getProfile();
  const before = await mockPallyApi.getSubscription();
  const anotherUser = randomUUID();
  await rejects(mockPallyApi.createCheckout(checkoutInput, anotherUser), isUnauthorized);
  await rejects(mockPallyApi.cancelSubscription(anotherUser), isUnauthorized);
  await rejects(mockPallyApi.refreshSubscription(anotherUser), isUnauthorized);
  deepEqual(await mockPallyApi.getSubscription(), before, "Rejected billing actions leave mock state unchanged");
  deepEqual(await mockPallyApi.refreshSubscription(profile.id), before);
  resetMockPallyApi();
}

async function main(): Promise<void> {
  await checkHttpBinding();
  await checkMockBinding();
  console.log("Billing account binding checks passed: checkout, cancel and refresh reject changed sessions with zero fetches.");
}

main().catch((error: unknown) => {
  console.error("Billing account binding check failed:", error);
  process.exit(1);
});
