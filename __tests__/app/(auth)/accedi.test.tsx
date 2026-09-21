import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AccediScreen from '@/app/(auth)/accedi';
import { signIn } from '@/src/features/auth/api';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

afterEach(cleanup);

jest.mock('expo-router', () => ({
  router: { replace: jest.fn(), push: jest.fn(), back: jest.fn() },
}));

jest.mock('@/src/features/auth/api', () => ({
  signIn: jest.fn(),
}));

jest.mock('@/src/features/auth/SessionProvider', () => ({
  useSessionContext: jest.fn(),
}));

const mockedSignIn = signIn as unknown as jest.Mock;
const mockedUseSessionContext = useSessionContext as unknown as jest.Mock;

function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AccediScreen />
    </QueryClientProvider>,
  );
}

describe('AccediScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows the invalid-credentials message when sign-in fails', async () => {
    mockedUseSessionContext.mockReturnValue({ refresh: jest.fn(), deactivated: false });
    mockedSignIn.mockResolvedValue({ ok: false, message: 'Email o password non corretti.' });

    await renderScreen();
    await fireEvent.changeText(screen.getByLabelText('Email'), 'a@b.com');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'secret123');
    await fireEvent.press(screen.getByRole('button', { name: 'Entra' }));

    await waitFor(() => expect(screen.getByText('Email o password non corretti.')).toBeTruthy());
  });

  it('refreshes the session and navigates to the product list on success', async () => {
    const refresh = jest.fn().mockResolvedValue(undefined);
    mockedUseSessionContext.mockReturnValue({ refresh, deactivated: false });
    mockedSignIn.mockResolvedValue({ ok: true, profile: {} });
    const { router } = require('expo-router');

    await renderScreen();
    await fireEvent.changeText(screen.getByLabelText('Email'), 'a@b.com');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'secret123');
    await fireEvent.press(screen.getByRole('button', { name: 'Entra' }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(router.replace).toHaveBeenCalledWith('/(app)/(tabs)/prodotti');
  });

  it('shows the deactivated message when the session says so', async () => {
    mockedUseSessionContext.mockReturnValue({ refresh: jest.fn(), deactivated: true });
    await renderScreen();
    expect(screen.getByText('Il tuo account è stato disattivato. Contatta il titolare.')).toBeTruthy();
  });
});
