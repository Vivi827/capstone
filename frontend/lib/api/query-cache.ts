type CacheEntry<T> = {
  expiresAt: number;
  promise?: Promise<T>;
  value?: T;
};

const MAX_ENTRIES = 100;
const entries = new Map<string, CacheEntry<unknown>>();

function scopedKey(userId: string, key: string): string {
  return `${userId}:${key}`;
}

function enforceLimit(): void {
  while (entries.size > MAX_ENTRIES) {
    const oldestKey = entries.keys().next().value as string | undefined;
    if (!oldestKey) return;
    entries.delete(oldestKey);
  }
}

export function peek<T>(userId: string, key: string): T | undefined {
  const entry = entries.get(scopedKey(userId, key)) as CacheEntry<T> | undefined;
  return entry && entry.expiresAt > Date.now() ? entry.value : undefined;
}

export async function read<T>(
  userId: string,
  key: string,
  ttlMs: number,
  loader: () => Promise<T>,
): Promise<T> {
  const keyWithScope = scopedKey(userId, key);
  const existing = entries.get(keyWithScope) as CacheEntry<T> | undefined;
  const now = Date.now();

  if (existing?.value !== undefined && existing.expiresAt > now) {
    return existing.value;
  }
  if (existing?.promise) return existing.promise;

  const nextEntry: CacheEntry<T> = {
    expiresAt: existing?.expiresAt ?? 0,
    value: existing?.value,
  };
  const promise = loader()
    .then((value) => {
      if (entries.get(keyWithScope) === nextEntry) {
        entries.delete(keyWithScope);
        entries.set(keyWithScope, { expiresAt: Date.now() + ttlMs, value });
        enforceLimit();
      }
      return value;
    })
    .catch((error: unknown) => {
      if (entries.get(keyWithScope) === nextEntry) entries.delete(keyWithScope);
      throw error;
    });

  nextEntry.promise = promise;
  entries.set(keyWithScope, nextEntry);
  enforceLimit();
  return promise;
}

export async function prefetch<T>(
  userId: string,
  key: string,
  ttlMs: number,
  loader: () => Promise<T>,
): Promise<void> {
  await read(userId, key, ttlMs, loader);
}

export function write<T>(userId: string, key: string, ttlMs: number, value: T): void {
  const keyWithScope = scopedKey(userId, key);
  entries.delete(keyWithScope);
  entries.set(keyWithScope, { expiresAt: Date.now() + ttlMs, value });
  enforceLimit();
}

export function invalidate(userId: string, keyPrefix: string): void {
  const scopedPrefix = scopedKey(userId, keyPrefix);
  entries.forEach((_entry, key) => {
    if (key.startsWith(scopedPrefix)) entries.delete(key);
  });
}

export function clearUser(userId: string): void {
  const prefix = `${userId}:`;
  entries.forEach((_entry, key) => {
    if (key.startsWith(prefix)) entries.delete(key);
  });
}
