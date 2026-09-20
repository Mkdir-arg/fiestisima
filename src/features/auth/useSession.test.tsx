import { renderHook, waitFor, cleanup, act } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useSession, useSignOut } from './useSession';
import { api, ApiError } from '@/src/lib/api';
import { tokenStorage } from '@/src/lib/tokenStorage';

// Without `gcTime: 0` a QueryClient schedules a garbage-collection timer
// (minutes long) per query that outlives the test and keeps the Jest
// process alive; `cleanup()` unmounts the hook so that timer is scheduled
// promptly instead of never.
afterEach(async () => {
  await cleanup();
});

// Only the network methods are mocked; ApiError/detailCode stay the real
// implementation from src/lib/api.ts, since useSession's error handling
// depends on `instanceof ApiError` and on reading `.status`/`.detail`.
jest.mock('@/src/lib/api', () => {
  const actual = jest.requireActual('@/src/lib/api');
  return {
    ...actual,
    api: {
      get: jest.fn(),
      post: jest.fn(),
      patch: jest.fn(),
      del: jest.fn(),
    },
  };
});

jest.mock('@/src/lib/tokenStorage', () => ({
  tokenStorage: {
    getTokens: jest.fn(),
    setTokens: jest.fn(),
    clear: jest.fn(),
  },
}));

const mockedApi = api as jest.Mocked<typeof api>;
const mockedTokenStorage = tokenStorage as jest.Mocked<typeof tokenStorage>;

// Captured by `wrapper` on each render so a test can spy on the exact
// QueryClient instance the hook under test is using.
let queryClient: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const profile = {
  id: 'u1',
  business_id: 'b1',
  full_name: 'Anna Ricci',
  role: 'titolare',
  active: true,
  business: { id: 'b1', name: 'Fiestisima', expiry_threshold_days: 7 },
};

describe('useSession', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedTokenStorage.clear.mockResolvedValue(undefined);
  });

  it('returns a null session when nobody signed in', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue(null);
    const { result } = await renderHook(() => useSession(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.session).toBeNull();
    expect(result.current.profile).toBeNull();
  });

  it('loads the profile when tokens are present', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue({ access: 'acc-1', refresh: 'ref-1' });
    mockedApi.get.mockResolvedValue(profile);
    const { result } = await renderHook(() => useSession(), { wrapper });
    await waitFor(() => expect(result.current.profile).not.toBeNull());
    expect(result.current.session).toEqual({ accessToken: 'acc-1' });
    expect(result.current.profile?.role).toBe('titolare');
  });

  it('clears the session and flags deactivated on 403 deactivated', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue({ access: 'acc-1', refresh: 'ref-1' });
    mockedApi.get.mockRejectedValue(new ApiError(403, 'deactivated'));
    const { result } = await renderHook(() => useSession(), { wrapper });
    await waitFor(() => expect(result.current.deactivated).toBe(true));
    expect(result.current.session).toBeNull();
    expect(mockedTokenStorage.clear).toHaveBeenCalled();
  });

  it('drops the cached profile once deactivation clears the session', async () => {
    // A valid session first, so react-query actually has a `['me']` entry
    // with data cached — the bug this guards against is that stale `data`
    // keeps being served after the session goes away.
    mockedTokenStorage.getTokens.mockResolvedValue({ access: 'acc-1', refresh: 'ref-1' });
    mockedApi.get.mockResolvedValueOnce(profile);
    const { result } = await renderHook(() => useSession(), { wrapper });
    await waitFor(() => expect(result.current.profile).not.toBeNull());

    mockedApi.get.mockRejectedValue(new ApiError(403, 'deactivated'));
    await act(async () => {
      await result.current.refresh();
    });
    await waitFor(() => expect(result.current.session).toBeNull());

    expect(result.current.profile).toBeNull();
    expect(result.current.deactivated).toBe(true);
  });
});

describe('useSignOut', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedTokenStorage.clear.mockResolvedValue(undefined);
  });

  it('clears local tokens and the whole query cache', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue(null);
    const { result } = await renderHook(() => useSignOut(), { wrapper });
    const clearSpy = jest.spyOn(queryClient, 'clear');

    await act(async () => {
      await result.current();
    });

    expect(mockedTokenStorage.clear).toHaveBeenCalled();
    expect(clearSpy).toHaveBeenCalled();
  });
});
