import { render, screen, cleanup, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import InvitoScreen from '@/app/(auth)/invito/[token]';
import { getInvitationPreview } from '@/src/features/auth/api';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

afterEach(cleanup);

jest.mock('expo-router', () => ({
  router: { replace: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({ token: 'tok-1' })),
}));

jest.mock('@/src/features/auth/api', () => ({
  getInvitationPreview: jest.fn(),
  acceptInvitation: jest.fn(),
}));

jest.mock('@/src/features/auth/SessionProvider', () => ({
  useSessionContext: jest.fn(() => ({ refresh: jest.fn() })),
}));

const mockedPreview = getInvitationPreview as unknown as jest.Mock;

function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <InvitoScreen />
    </QueryClientProvider>,
  );
}

describe('InvitoScreen', () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders the invitee name and business from the preview', async () => {
    mockedPreview.mockResolvedValue({
      ok: true,
      preview: { full_name: 'Marco Prova', business_name: 'Fiestisima', expires_at: '2030-01-01T00:00:00Z' },
    });

    await renderScreen();

    await waitFor(() => expect(screen.getByText('Marco Prova · Fiestisima')).toBeTruthy());
  });

  it('shows the expired message when the preview lookup fails', async () => {
    mockedPreview.mockResolvedValue({
      ok: false,
      message: 'Questo invito è scaduto. Chiedine uno nuovo al titolare.',
    });

    await renderScreen();

    await waitFor(() =>
      expect(screen.getByText('Questo invito è scaduto. Chiedine uno nuovo al titolare.')).toBeTruthy(),
    );
  });
});
