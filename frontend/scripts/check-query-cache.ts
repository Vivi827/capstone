import assert from "node:assert/strict";

import { clearUser, invalidate, peek, read, write } from "../lib/api/query-cache";

async function main(): Promise<void> {
  write("peek-user", "history:first", 60_000, { items: [] });
  assert.deepEqual(peek("peek-user", "history:first"), { items: [] }, "empty history is valid cached data");
  assert.equal(peek("other-user", "history:first"), undefined, "peek must stay scoped to the current user");
  write("peek-user", "history:latest", 0, "expired");
  assert.equal(peek("peek-user", "history:latest"), undefined, "peek must not serve expired values");
  invalidate("peek-user", "history:");
  assert.equal(peek("peek-user", "history:first"), undefined, "conversation changes must invalidate peeked history");
  clearUser("peek-user");

  let calls = 0;
  let resolveLoader: (value: string) => void = () => {
    throw new Error("loader resolver was not created");
  };
  const loader = () => {
    calls += 1;
    return new Promise<string>((resolve) => {
      resolveLoader = resolve;
    });
  };

  const first = read("user-a", "profile", 60_000, loader);
  const duplicate = read("user-a", "profile", 60_000, loader);
  assert.equal(calls, 1, "concurrent reads must share one loader");
  resolveLoader("Claire");
  assert.deepEqual(await Promise.all([first, duplicate]), ["Claire", "Claire"]);

  const cached = await read("user-a", "profile", 60_000, async () => {
    calls += 1;
    return "unexpected";
  });
  assert.equal(cached, "Claire");
  assert.equal(calls, 1, "fresh values must be served from cache");

  invalidate("user-a", "profile");
  const refreshed = await read("user-a", "profile", 60_000, async () => {
    calls += 1;
    return "Lee";
  });
  assert.equal(refreshed, "Lee");
  assert.equal(calls, 2, "invalidated values must reload");

  await read("user-b", "profile", 60_000, async () => "Other user");
  clearUser("user-a");
  const isolated = await read("user-b", "profile", 60_000, async () => "unexpected");
  assert.equal(isolated, "Other user", "clearing one user must not affect another user");

  const expiringKey = `usage-${crypto.randomUUID()}`;
  await read("user-a", expiringKey, 0, async () => 1);
  const expired = await read("user-a", expiringKey, 60_000, async () => 2);
  assert.equal(expired, 2, "expired values must reload");

  let resolveStaleRequest: (value: string) => void = () => {
    throw new Error("stale request resolver was not created");
  };
  const staleRequest = read("user-a", "history:first", 60_000, () => (
    new Promise<string>((resolve) => {
      resolveStaleRequest = resolve;
    })
  ));
  invalidate("user-a", "history:");
  resolveStaleRequest("stale");
  assert.equal(await staleRequest, "stale");
  const afterRace = await read("user-a", "history:first", 60_000, async () => "fresh");
  assert.equal(afterRace, "fresh", "invalidated in-flight requests must not repopulate cache");

  let resolveOldProfile!: (value: string) => void;
  invalidate("user-a", "profile");
  const oldProfile = read("user-a", "profile", 60_000, () => new Promise<string>((resolve) => {
    resolveOldProfile = resolve;
  }));
  write("user-a", "profile", 60_000, "B2");
  const unexpectedReload = async (): Promise<string> => {
    throw new Error("saved profiles must not be fetched again");
  };
  assert.equal(await read("user-a", "profile", 60_000, unexpectedReload), "B2");
  resolveOldProfile("B1");
  await oldProfile;
  assert.equal(await read("user-a", "profile", 60_000, unexpectedReload), "B2", "older reads must not overwrite saved profiles");
  assert.equal(await read("user-b", "profile", 60_000, unexpectedReload), "Other user", "writes must stay scoped to the current user");

  clearUser("user-a");
  clearUser("user-b");
  console.log("Query cache checks passed");
}

void main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
