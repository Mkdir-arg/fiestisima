import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

/** iOS SecureStore warns above 2048 bytes. Values are chunked below that. */
export const CHUNK_SIZE = 1800;

export function chunk(value: string): string[] {
  if (value.length <= CHUNK_SIZE) return [value];
  const parts: string[] = [];
  for (let i = 0; i < value.length; i += CHUNK_SIZE) {
    parts.push(value.slice(i, i + CHUNK_SIZE));
  }
  return parts;
}

export function unchunk(parts: string[]): string {
  return parts.join('');
}

const countKey = (key: string) => `${key}__count`;
const partKey = (key: string, i: number) => `${key}__${i}`;

/**
 * On the web the session lives in localStorage, the only thing available
 * there. On the phone it lives in the system keychain, chunked. Never in
 * AsyncStorage: the refresh token would end up in plain text.
 */
async function getItem(key: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    try {
      return globalThis.localStorage?.getItem(key) ?? null;
    } catch {
      return null;
    }
  }
  const raw = await SecureStore.getItemAsync(countKey(key));
  if (raw === null) return null;
  const count = Number(raw);
  const parts: string[] = [];
  for (let i = 0; i < count; i++) {
    const part = await SecureStore.getItemAsync(partKey(key, i));
    if (part === null) return null;
    parts.push(part);
  }
  return unchunk(parts);
}

async function removeItem(key: string): Promise<void> {
  if (Platform.OS === 'web') {
    try {
      globalThis.localStorage?.removeItem(key);
    } catch {
      /* nothing to remove */
    }
    return;
  }
  const raw = await SecureStore.getItemAsync(countKey(key));
  if (raw === null) return;
  const count = Number(raw);
  for (let i = 0; i < count; i++) {
    await SecureStore.deleteItemAsync(partKey(key, i));
  }
  await SecureStore.deleteItemAsync(countKey(key));
}

async function setItem(key: string, value: string): Promise<void> {
  if (Platform.OS === 'web') {
    try {
      globalThis.localStorage?.setItem(key, value);
    } catch {
      /* private mode or blocked storage: the session lasts as long as the tab */
    }
    return;
  }
  await removeItem(key);
  const parts = chunk(value);
  await SecureStore.setItemAsync(countKey(key), String(parts.length));
  for (let i = 0; i < parts.length; i++) {
    await SecureStore.setItemAsync(partKey(key, i), parts[i]!);
  }
}

const ACCESS_KEY = 'fiestisima.access';
const REFRESH_KEY = 'fiestisima.refresh';

export type TokenPair = { access: string; refresh: string };

export const tokenStorage = {
  async getTokens(): Promise<TokenPair | null> {
    const [access, refresh] = await Promise.all([getItem(ACCESS_KEY), getItem(REFRESH_KEY)]);
    if (!access || !refresh) return null;
    return { access, refresh };
  },

  async setTokens({ access, refresh }: TokenPair): Promise<void> {
    await Promise.all([setItem(ACCESS_KEY, access), setItem(REFRESH_KEY, refresh)]);
  },

  async clear(): Promise<void> {
    await Promise.all([removeItem(ACCESS_KEY), removeItem(REFRESH_KEY)]);
  },
};
