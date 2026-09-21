import { render, screen, cleanup } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ProdottiScreen from '@/app/(app)/(tabs)/prodotti';
import { useProducts } from '@/src/features/products/queries';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

afterEach(cleanup);

jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn() },
}));

jest.mock('@/src/features/products/queries', () => ({
  useProducts: jest.fn(),
}));

jest.mock('@/src/features/auth/SessionProvider', () => ({
  useSessionContext: jest.fn(),
}));

const mockedUseProducts = useProducts as unknown as jest.Mock;
const mockedUseSessionContext = useSessionContext as unknown as jest.Mock;

function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ProdottiScreen />
    </QueryClientProvider>,
  );
}

describe('ProdottiScreen', () => {
  beforeEach(() => jest.clearAllMocks());

  it('shows the empty state when there are no products', async () => {
    mockedUseProducts.mockReturnValue({ data: [], isLoading: false, error: null });
    mockedUseSessionContext.mockReturnValue({ profile: { role: 'titolare' } });

    await renderScreen();

    expect(screen.getByText('Nessun prodotto. Aggiungi il primo.')).toBeTruthy();
  });

  it('renders product rows', async () => {
    mockedUseProducts.mockReturnValue({
      data: [
        { id: 'p1', name: 'Farina 00', barcode: null, storage: 'dispensa', unit: 'kg', min_stock: 2 },
        { id: 'p2', name: 'Pomodori pelati', barcode: '800123', storage: 'dispensa', unit: 'pz', min_stock: 6 },
      ],
      isLoading: false,
      error: null,
    });
    mockedUseSessionContext.mockReturnValue({ profile: { role: 'titolare' } });

    await renderScreen();

    expect(screen.getByText('Farina 00')).toBeTruthy();
    expect(screen.getByText('Pomodori pelati')).toBeTruthy();
  });

  it('hides "Nuovo prodotto" for an operatore', async () => {
    mockedUseProducts.mockReturnValue({ data: [], isLoading: false, error: null });
    mockedUseSessionContext.mockReturnValue({ profile: { role: 'operatore' } });

    await renderScreen();

    expect(screen.queryByText('Nuovo prodotto')).toBeNull();
  });

  it('shows "Nuovo prodotto" for a titolare', async () => {
    mockedUseProducts.mockReturnValue({ data: [], isLoading: false, error: null });
    mockedUseSessionContext.mockReturnValue({ profile: { role: 'titolare' } });

    await renderScreen();

    expect(screen.getByText('Nuovo prodotto')).toBeTruthy();
  });
});
