import { useCallback, useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, detailCode } from '@/src/lib/api';
import { tokenStorage } from '@/src/lib/tokenStorage';
import { signOut } from './api';
import type { components } from '@/src/types/api';

export type Profile = components['schemas']['ProfileOut'];
export type Session = { accessToken: string };

/**
 * Same public shape as plan v1: `{ session, profile, isLoading }`, plus
 * `refresh()` (so callers can force a re-check after sign-in/out) and
 * `deactivated` (403 `deactivated` from `/auth/me` needs a dedicated message,
 * not just "you're signed out").
 */
export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [checked, setChecked] = useState(false);
  const [deactivated, setDeactivated] = useState(false);
  const queryClient = useQueryClient();

  const loadTokens = useCallback(async () => {
    const tokens = await tokenStorage.getTokens();
    setSession(tokens ? { accessToken: tokens.access } : null);
    setChecked(true);
  }, []);

  useEffect(() => {
    loadTokens();
  }, [loadTokens]);

  const meQuery = useQuery({
    queryKey: ['me'],
    enabled: Boolean(session),
    retry: false,
    queryFn: () => api.get<Profile>('/auth/me'),
  });

  useEffect(() => {
    if (!meQuery.isError) return;
    // By the time /auth/me errors here, src/lib/api.ts has already tried one
    // refresh-and-retry internally. A 401 here means that refresh also
    // failed (or there was no refresh token); a 403 `deactivated` means the
    // access token is still technically valid but the account was disabled.
    // Either way there is no usable session left: clear tokens and drop out.
    const status = meQuery.error instanceof ApiError ? meQuery.error.status : null;
    const code = detailCode(meQuery.error);
    if (status === 403 && code === 'deactivated') {
      setDeactivated(true);
    }
    tokenStorage.clear().then(() => {
      setSession(null);
    });
  }, [meQuery.isError, meQuery.error]);

  useEffect(() => {
    // Once there is no session — whether from the error effect above or
    // from a caller nulling it out — drop the cached profile too. Without
    // this, a stale `['me']` entry can keep answering `meQuery.data` after
    // sign-out/deactivation until something else happens to refetch it.
    if (session === null) {
      queryClient.removeQueries({ queryKey: ['me'] });
    }
  }, [session, queryClient]);

  const refresh = useCallback(async () => {
    setDeactivated(false);
    await loadTokens();
    await queryClient.invalidateQueries({ queryKey: ['me'] });
  }, [loadTokens, queryClient]);

  return {
    session,
    // Never surface a cached profile once there is no session: react-query
    // keeps the last successful `data` around after an error unless the
    // query is removed, which would otherwise flash the previous user's
    // profile for a tick after sign-out or deactivation.
    profile: session ? meQuery.data ?? null : null,
    isLoading: !checked || (Boolean(session) && meQuery.isLoading),
    deactivated,
    refresh,
  };
}

/**
 * Signs out and drops every cached query, not just `['me']` — otherwise the
 * next person to sign in on this device (or this same person signing back
 * in) would see the previous session's `['products']` etc. flash before
 * being refetched.
 */
export function useSignOut() {
  const queryClient = useQueryClient();
  return useCallback(async () => {
    await signOut();
    queryClient.clear();
  }, [queryClient]);
}
