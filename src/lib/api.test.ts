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

  it('refreshes once on 401 and retries the original request', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue({ access: 'stale', refresh: 'ref-1' });
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(jsonResponse(401, 'invalid_token')) // original request
      .mockResolvedValueOnce(jsonResponse(200, { access_token: 'fresh', refresh_token: 'ref-2' })) // refresh
      .mockResolvedValueOnce(jsonResponse(200, { id: '1' })); // retried request

    const result = await api.get<{ id: string }>('/products/1');

    expect(result).toEqual({ id: '1' });
    expect(global.fetch).toHaveBeenCalledTimes(3);
    expect(mockedTokenStorage.setTokens).toHaveBeenCalledWith({ access: 'fresh', refresh: 'ref-2' });
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
      return Promise.resolve(count === 1 ? jsonResponse(401, 'invalid_token') : jsonResponse(200, { ok: true }));
    });

    await Promise.all([api.get('/a'), api.get('/b')]);

    expect(refreshCalls).toBe(1);
  });

  it('clears tokens and throws ApiError(401) when the refresh itself is rejected', async () => {
    mockedTokenStorage.getTokens.mockResolvedValue({ access: 'stale', refresh: 'bad-refresh' });
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(jsonResponse(401, 'invalid_token')) // original request
      .mockResolvedValueOnce(jsonResponse(401, 'invalid_token')); // refresh fails too

    await expect(api.get('/products')).rejects.toMatchObject({ status: 401 });
    expect(mockedTokenStorage.clear).toHaveBeenCalled();
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
