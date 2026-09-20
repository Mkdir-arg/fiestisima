import { api, ApiError, detailCode } from './api';
import { tokenStorage } from './tokenStorage';

jest.mock('./tokenStorage', () => ({
  tokenStorage: {
    getTokens: jest.fn(),
    setTokens: jest.fn(),
    clear: jest.fn(),
  },
}));

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}

const mockedTokenStorage = tokenStorage as jest.Mocked<typeof tokenStorage>;

describe('api', () => {
  beforeEach(() => {
    jest.resetAllMocks();
    global.fetch = jest.fn();
  });

  it('attaches the bearer token when one is stored', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue({ access: 'acc-1', refresh: 'ref-1' });
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(200, { ok: true }));

    await api.get('/products');

    const [, init] = (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer acc-1');
  });

  it('unwraps FastAPI\'s {"detail": ...} envelope into ApiError.detail', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue(null);
    (global.fetch as jest.Mock).mockResolvedValue(
      jsonResponse(409, { detail: { code: 'barcode_taken', name: 'Farina 00' } }),
    );

    const err = await api.post('/products', { name: 'x' }).catch((e) => e);

    expect(err).toBeInstanceOf(ApiError);
    expect(detailCode(err)).toBe('barcode_taken');
    expect((err as ApiError).detail).toEqual({ code: 'barcode_taken', name: 'Farina 00' });
  });

  it('refreshes once on 401 and retries the original request with the new bearer', async () => {
    mockedTokenStorage.getTokens
      .mockResolvedValueOnce({ access: 'stale', refresh: 'ref-1' }) // original request
      .mockResolvedValueOnce({ access: 'stale', refresh: 'ref-1' }) // re-check before refreshing
      .mockResolvedValue({ access: 'fresh', refresh: 'ref-2' }); // retried request, after refresh
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'invalid_token' })) // original request
      .mockResolvedValueOnce(jsonResponse(200, { access_token: 'fresh', refresh_token: 'ref-2' })) // refresh
      .mockResolvedValueOnce(jsonResponse(200, { id: '1' })); // retried request

    const result = await api.get<{ id: string }>('/products/1');

    expect(result).toEqual({ id: '1' });
    expect(global.fetch).toHaveBeenCalledTimes(3);
    expect(mockedTokenStorage.setTokens).toHaveBeenCalledWith({ access: 'fresh', refresh: 'ref-2' });
    const [, retryInit] = (global.fetch as jest.Mock).mock.calls[2] as [string, RequestInit];
    expect((retryInit.headers as Record<string, string>).Authorization).toBe('Bearer fresh');
  });

  it('deduplicates two concurrent 401s into a single refresh call', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue({ access: 'stale', refresh: 'ref-1' });
    let refreshCalls = 0;
    // Each path's first call gets a 401 (stale token); the retry after
    // refresh succeeds.
    const nonRefreshCallsPerPath = new Map<string, number>();
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1;
        return Promise.resolve(jsonResponse(200, { access_token: 'fresh', refresh_token: 'ref-2' }));
      }
      const count = (nonRefreshCallsPerPath.get(url) ?? 0) + 1;
      nonRefreshCallsPerPath.set(url, count);
      return Promise.resolve(
        count === 1 ? jsonResponse(401, { detail: 'invalid_token' }) : jsonResponse(200, { ok: true }),
      );
    });

    await Promise.all([api.get('/a'), api.get('/b')]);

    expect(refreshCalls).toBe(1);
  });

  it('does not start a second refresh when another request already rotated the tokens', async () => {
    // Simulates the real-world window the guard exists for: A's 401
    // arrives, refreshes, and its ENTIRE retry completes — at which point
    // `refreshInFlight` has already been reset to null by `.finally`. Only
    // THEN does B's 401 (for its own request, made with the same original,
    // now-stale token) arrive. Without the guard, B would find no
    // in-flight refresh to piggyback on and would kick off a brand new one
    // with its own now-stale refresh token.
    //
    // Gating B's 401 merely on `setTokens` having been called (as an
    // earlier version of this test did) is NOT equivalent: at that point
    // `refreshInFlight` is still set, so B would piggyback on it via the
    // dedup path regardless of this guard, and deleting the guard would
    // not turn this test red. Gating on A's whole `api.get('/a')` having
    // resolved (its retry included) is what actually exercises the guard.
    let stored = { access: 'stale', refresh: 'ref-1' };
    let markASettled!: () => void;
    const aSettled = new Promise<void>((resolve) => {
      markASettled = resolve;
    });
    mockedTokenStorage.getTokens.mockImplementation(() => Promise.resolve(stored));
    mockedTokenStorage.setTokens.mockImplementation((pair: { access: string; refresh: string }) => {
      stored = pair;
      return Promise.resolve();
    });

    let refreshCalls = 0;
    const callsPerPath = new Map<string, number>();
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.endsWith('/auth/refresh')) {
        refreshCalls += 1;
        return Promise.resolve(jsonResponse(200, { access_token: 'fresh', refresh_token: 'ref-2' }));
      }
      const count = (callsPerPath.get(url) ?? 0) + 1;
      callsPerPath.set(url, count);
      if (url.endsWith('/b') && count === 1) {
        return aSettled.then(() => jsonResponse(401, { detail: 'invalid_token' }));
      }
      return Promise.resolve(
        count === 1 ? jsonResponse(401, { detail: 'invalid_token' }) : jsonResponse(200, { ok: true }),
      );
    });

    const a = api.get('/a').then((r) => {
      markASettled();
      return r;
    });
    const b = api.get('/b');
    await Promise.all([a, b]);

    expect(refreshCalls).toBe(1);
    const bRetryCall = (global.fetch as jest.Mock).mock.calls.find(
      ([url, init]: [string, RequestInit]) =>
        url.endsWith('/b') && (init.headers as Record<string, string>).Authorization === 'Bearer fresh',
    );
    expect(bRetryCall).toBeDefined();
  });

  it('clears tokens and throws ApiError(401) when the refresh itself is rejected', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue({ access: 'stale', refresh: 'bad-refresh' });
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'invalid_token' })) // original request
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'invalid_token' })); // refresh fails too

    await expect(api.get('/products')).rejects.toMatchObject({ status: 401 });
    expect(mockedTokenStorage.clear).toHaveBeenCalled();
  });

  it('never attaches a bearer or triggers a refresh for an auth:false call, even on 401', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue({ access: 'stale', refresh: 'ref-1' });
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(401, { detail: 'invalid_credentials' }));

    await expect(
      api.post('/auth/login', { email: 'a@b.com', password: 'x' }, { auth: false }),
    ).rejects.toMatchObject({ status: 401, detail: 'invalid_credentials' });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [, init] = (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  describe('detailCode', () => {
    it('reads a string detail', () => {
      expect(detailCode(new ApiError(401, 'invalid_token'))).toBe('invalid_token');
    });

    it('reads .code from an object detail', () => {
      expect(detailCode(new ApiError(409, { code: 'barcode_taken', name: 'Farina' }))).toBe(
        'barcode_taken',
      );
    });

    it('returns null for a pydantic 422 list detail', () => {
      expect(detailCode(new ApiError(422, [{ loc: ['body', 'email'], msg: 'invalid', type: 'value_error' }]))).toBeNull();
    });

    it('returns null for a non-ApiError', () => {
      expect(detailCode(new Error('boom'))).toBeNull();
    });
  });
});
