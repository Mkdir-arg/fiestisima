import { render, screen, fireEvent, cleanup } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { router } from 'expo-router';
import OggiScreen from '@/app/(app)/(tabs)/oggi';
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
      <OggiScreen />
    </QueryClientProvider>,
  );
}

describe('OggiScreen', () => {
  beforeEach(() => jest.clearAllMocks());

  it('greets with the business name', async () => {
    mockedUseProducts.mockReturnValue({ data: [], isLoading: false });
    mockedUseSessionContext.mockReturnValue({
      profile: { role: 'titolare', business: { name: 'Il Giardino' } },
    });

    await renderScreen();

    expect(screen.getByText('Ciao! Ecco lo stato di Il Giardino.')).toBeOnTheScreen();
  });

  it('shows the real product count and placeholders for what is not built yet', async () => {
    mockedUseProducts.mockReturnValue({
      data: [{ id: 'p1' }, { id: 'p2' }, { id: 'p3' }],
      isLoading: false,
    });
    mockedUseSessionContext.mockReturnValue({
      profile: { role: 'titolare', business: { name: 'Il Giardino' } },
    });

    await renderScreen();

    expect(screen.getByText('3')).toBeOnTheScreen();
    expect(screen.getAllByText('—').length).toBe(2);
    expect(screen.getAllByText('Arriva col Blocco A').length).toBe(2);
  });

  it('hides the "Nuovo prodotto" quick action for an operatore', async () => {
    mockedUseProducts.mockReturnValue({ data: [], isLoading: false });
    mockedUseSessionContext.mockReturnValue({
      profile: { role: 'operatore', business: { name: 'Il Giardino' } },
    });

    await renderScreen();

    expect(screen.queryByRole('button', { name: 'Nuovo prodotto' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Cerca un prodotto' })).toBeTruthy();
  });

  it('navigates to the products list from the search quick action', async () => {
    mockedUseProducts.mockReturnValue({ data: [], isLoading: false });
    mockedUseSessionContext.mockReturnValue({
      profile: { role: 'titolare', business: { name: 'Il Giardino' } },
    });

    await renderScreen();
    await fireEvent.press(screen.getByRole('button', { name: 'Cerca un prodotto' }));

    expect(router.push).toHaveBeenCalledWith('/(app)/(tabs)/prodotti');
  });
});
