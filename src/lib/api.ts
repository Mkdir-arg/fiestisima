import { tokenStorage } from './tokenStorage';
import type { paths } from '@/src/types/api';

const API_URL = process.env.EXPO_PUBLIC_API_URL;

if (!API_URL) {
  throw new Error(
    'Missing EXPO_PUBLIC_API_URL. Copy .env.example to .env.local and set it.',
  );
}

/**
 * `detail` is a machine-readable string code for almost every error, except
 * pydantic's 422 (a list of `{loc, msg, type}`) and the products 409 for a
 * duplicate barcode, which is an object `{code, name}`. Callers must not
 * assume a shape; use `detailCode` below to read the code out of any of them.
 */
export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/** Returns the machine code out of an error's `detail`, whatever its shape. */
export function detailCode(err: unknown): string | null {
  if (!(err instanceof ApiError)) return null;
  const { detail } = err;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const code = (detail as { code: unknown }).code;
    return typeof code === 'string' ? code : null;
  }
  return null;
}

/**
 * FastAPI's default error handler always wraps the payload as
 * `{"detail": ...}` — `{"detail":"invalid_credentials"}`,
 * `{"detail":{"code":"barcode_taken","name":"..."}}`, or a pydantic 422's
 * `{"detail":[...]}`. Only error bodies are wrapped this way (a 2xx body is
 * never touched), so this is only ever applied where `!response.ok`.
 */
function extractDetail(body: unknown): unknown {
  if (body && typeof body === 'object' && 'detail' in body) {
    return (body as { detail: unknown }).detail;
  }
  return body;
}

type RefreshResponse = paths['/auth/refresh']['post']['responses'][200]['content']['application/json'];

/**
 * At most one refresh runs at a time: N requests that all hit a 401
 * concurrently share this single promise instead of each calling
 * `/auth/refresh`. The refresh token is single-use (the server rotates it on
 * every call), so a second concurrent refresh with the same, now-stale
 * token would itself come back 401 and log the user out.
 */
let refreshInFlight: Promise<string> | null = null;

async function doRefresh(refreshToken: string): Promise<string> {
  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  const body = await parseBody(response);
  if (!response.ok) {
    await tokenStorage.clear();
    throw new ApiError(response.status, extractDetail(body));
  }
  const pair = body as RefreshResponse;
  await tokenStorage.setTokens({ access: pair.access_token, refresh: pair.refresh_token });
  return pair.access_token;
}

/** Runs the refresh, deduplicating concurrent callers onto one in-flight call. */
async function refreshAccessToken(refreshToken: string): Promise<string> {
  if (!refreshInFlight) {
    refreshInFlight = doRefresh(refreshToken).finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

type RequestOptions = {
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  /**
   * false for endpoints that are public or ARE the auth handshake itself
   * (login, refresh, logout, password reset, invitation preview/accept):
   * no bearer is attached, and a 401 from one of these never triggers a
   * refresh-and-retry (a wrong password on /auth/login with stale tokens
   * still lying around must surface `invalid_credentials`, not bounce
   * through a token refresh and come back as `invalid_token`).
   */
  auth?: boolean;
};

async function request<T>(path: string, options: RequestOptions, isRetry = false): Promise<T> {
  const useAuth = options.auth !== false;
  const tokens = useAuth ? await tokenStorage.getTokens() : null;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (tokens) {
    headers.Authorization = `Bearer ${tokens.access}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: options.method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (useAuth && response.status === 401 && !isRetry && tokens) {
    // Another request may have already refreshed while this one was in
    // flight: re-read storage before refreshing again. If the stored access
    // token no longer matches what this request sent, someone else already
    // rotated it — retry with the new one instead of calling /auth/refresh
    // a second time with our now-stale (single-use) refresh token, which
    // would itself 401 and log the user out.
    const stored = await tokenStorage.getTokens();
    if (stored && stored.access !== tokens.access) {
      return request<T>(path, options, true);
    }
    try {
      await refreshAccessToken(tokens.refresh);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(401, 'invalid_token');
    }
    return request<T>(path, options, true);
  }

  const body = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, extractDetail(body));
  }
  return body as T;
}

type CallOptions = { auth?: boolean };

export const api = {
  get<T>(path: string, options: CallOptions = {}): Promise<T> {
    return request<T>(path, { method: 'GET', auth: options.auth });
  },
  post<T>(path: string, body?: unknown, options: CallOptions = {}): Promise<T> {
    return request<T>(path, { method: 'POST', body, auth: options.auth });
  },
  patch<T>(path: string, body?: unknown, options: CallOptions = {}): Promise<T> {
    return request<T>(path, { method: 'PATCH', body, auth: options.auth });
  },
  del(path: string, options: CallOptions = {}): Promise<void> {
    return request<void>(path, { method: 'DELETE', auth: options.auth });
  },
};
