import { api, ApiError, detailCode } from '@/src/lib/api';
import { tokenStorage } from '@/src/lib/tokenStorage';
import { t } from '@/src/i18n/it';
import type { components } from '@/src/types/api';

type TokenPair = components['schemas']['TokenPair'];
type ProfileOut = components['schemas']['ProfileOut'];
type InvitationPreview = components['schemas']['InvitationPreview'];

export type AuthResult = { ok: true; profile: ProfileOut } | { ok: false; message: string };

// Machine codes the API sends as `detail` for auth-flow errors, mapped to the
// Italian copy in `t.auth`. Anything not listed here falls back to a generic
// message rather than leaking an English machine code to the screen.
const AUTH_MESSAGES: Record<string, string> = {
  invalid_credentials: t.auth.invalidCredentials,
  too_many_attempts: t.auth.tooManyAttempts,
  deactivated: t.auth.deactivated,
  invitation_expired: t.auth.invitationExpired,
  email_taken: t.auth.emailTaken,
  invalid_token: t.auth.invalidToken,
};

export function messageFor(code: string | null): string {
  if (code && code in AUTH_MESSAGES) return AUTH_MESSAGES[code]!;
  return t.errors.generic;
}

/**
 * A network failure (fetch rejecting with a TypeError — no connection, DNS,
 * CORS) never reaches src/lib/api.ts's ApiError path, so it must be told
 * apart from a real API error here: it gets the "you're offline" copy
 * instead of a generic or misleading message.
 */
function describeAuthError(err: unknown): string {
  if (!(err instanceof ApiError)) return t.auth.offline;
  return messageFor(detailCode(err));
}

async function storeTokenPair(pair: TokenPair): Promise<void> {
  await tokenStorage.setTokens({ access: pair.access_token, refresh: pair.refresh_token });
}

export async function signIn(email: string, password: string): Promise<AuthResult> {
  try {
    const pair = await api.post<TokenPair>('/auth/login', { email, password }, { auth: false });
    await storeTokenPair(pair);
    return { ok: true, profile: pair.profile };
  } catch (err) {
    return { ok: false, message: describeAuthError(err) };
  }
}

export async function signOut(): Promise<void> {
  const tokens = await tokenStorage.getTokens();
  if (tokens) {
    try {
      // Idempotent on the server even if the refresh token is already
      // expired or revoked; a failure here must never block local logout.
      // No Bearer either (see api contract): logout takes the refresh
      // token in the body, not the access token in the header.
      await api.post('/auth/logout', { refresh_token: tokens.refresh }, { auth: false });
    } catch {
      /* ignore: we clear the local session below regardless */
    }
  }
  await tokenStorage.clear();
}

export async function acceptInvitation(
  invitationToken: string,
  fullName: string,
  password: string,
): Promise<AuthResult> {
  try {
    const pair = await api.post<TokenPair>(
      `/invitations/${invitationToken}/accept`,
      { full_name: fullName, password },
      { auth: false },
    );
    await storeTokenPair(pair);
    return { ok: true, profile: pair.profile };
  } catch (err) {
    return { ok: false, message: describeAuthError(err) };
  }
}

export type InvitationPreviewResult =
  | { ok: true; preview: InvitationPreview }
  | { ok: false; message: string };

export async function getInvitationPreview(invitationToken: string): Promise<InvitationPreviewResult> {
  try {
    const preview = await api.get<InvitationPreview>(`/invitations/${invitationToken}`, { auth: false });
    return { ok: true, preview };
  } catch (err) {
    if (!(err instanceof ApiError)) {
      return { ok: false, message: t.auth.offline };
    }
    // 404 covers unknown/accepted/expired/cancelled alike (see api contract);
    // the screen shows one generic "invalid invitation" state either way.
    return { ok: false, message: t.invite.expired };
  }
}

export async function forgotPassword(email: string): Promise<void> {
  // The API always answers 202 {ok:true}, whether or not the address is
  // registered, so this never surfaces an error — that would confirm an
  // account exists.
  await api.post('/auth/password/forgot', { email }, { auth: false });
}

export type ResetPasswordResult = { ok: true } | { ok: false; message: string };

export async function resetPassword(token: string, password: string): Promise<ResetPasswordResult> {
  try {
    await api.post('/auth/password/reset', { token, password }, { auth: false });
    return { ok: true };
  } catch (err) {
    return { ok: false, message: describeAuthError(err) };
  }
}
