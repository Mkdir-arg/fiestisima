import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import NuovoProdottoScreen from '@/app/(app)/prodotti/nuovo';
import { useCreateProduct } from '@/src/features/products/mutations';

afterEach(cleanup);

jest.mock('expo-router', () => ({
  router: { back: jest.fn(), push: jest.fn() },
}));

jest.mock('@/src/features/products/mutations', () => ({
  useCreateProduct: jest.fn(),
}));

const mockedUseCreateProduct = useCreateProduct as unknown as jest.Mock;

function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NuovoProdottoScreen />
    </QueryClientProvider>,
  );
}

describe('NuovoProdottoScreen', () => {
  beforeEach(() => jest.clearAllMocks());

  it('shows the duplicate-barcode message when the mutation rejects with it', async () => {
    const mutateAsync = jest.fn().mockRejectedValue(new Error('Questo codice è già associato a "Farina 00".'));
    mockedUseCreateProduct.mockReturnValue({ mutateAsync, isPending: false });

    await renderScreen();
    await fireEvent.changeText(screen.getByLabelText('Nome'), 'Farina integrale');
    await fireEvent.press(screen.getByRole('button', { name: 'Salva' }));

    await waitFor(() =>
      expect(screen.getByText('Questo codice è già associato a "Farina 00".')).toBeTruthy(),
    );
  });

  it('shows the generic not-permitted message on a 403/404 write', async () => {
    const { ApiError } = require('@/src/lib/api');
    const mutateAsync = jest.fn().mockRejectedValue(new ApiError(403, 'forbidden'));
    mockedUseCreateProduct.mockReturnValue({ mutateAsync, isPending: false });

    await renderScreen();
    await fireEvent.changeText(screen.getByLabelText('Nome'), 'Farina integrale');
    await fireEvent.press(screen.getByRole('button', { name: 'Salva' }));

    await waitFor(() => expect(screen.getByText('Non hai il permesso per questa azione.')).toBeTruthy());
  });
});
