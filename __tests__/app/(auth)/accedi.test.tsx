import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AccediScreen from '@/app/(auth)/accedi';
import { forgotPassword, signIn } from '@/src/features/auth/api';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

afterEach(cleanup);

jest.mock('expo-router', () => ({
  router: { replace: jest.fn(), push: jest.fn(), back: jest.fn() },
}));

jest.mock('@/src/features/auth/api', () => ({
  signIn: jest.fn(),
  forgotPassword: jest.fn(),
}));

jest.mock('@/src/features/auth/SessionProvider', () => ({
  useSessionContext: jest.fn(),
}));

const mockedSignIn = signIn as unknown as jest.Mock;
const mockedForgotPassword = forgotPassword as unknown as jest.Mock;
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

  it('hides the password until the reveal toggle is pressed', async () => {
    mockedUseSessionContext.mockReturnValue({ refresh: jest.fn(), deactivated: false });
    await renderScreen();

    // The first password anyone types here is the 20 random characters the
    // bootstrap script printed, so being able to read it back matters.
    expect(screen.getByLabelText('Password').props.secureTextEntry).toBe(true);
    await fireEvent.press(screen.getByRole('button', { name: 'Mostra' }));
    expect(screen.getByLabelText('Password').props.secureTextEntry).toBe(false);
    await fireEvent.press(screen.getByRole('button', { name: 'Nascondi' }));
    expect(screen.getByLabelText('Password').props.secureTextEntry).toBe(true);
  });

  it('asks for the email before sending a reset, then sends it', async () => {
    mockedUseSessionContext.mockReturnValue({ refresh: jest.fn(), deactivated: false });
    mockedForgotPassword.mockResolvedValue(undefined);
    await renderScreen();

    await fireEvent.press(screen.getByRole('button', { name: 'Password dimenticata?' }));
    expect(mockedForgotPassword).not.toHaveBeenCalled();
    expect(screen.getByText('Scrivi prima la tua email, poi tocca di nuovo.')).toBeTruthy();

    await fireEvent.changeText(screen.getByLabelText('Email'), '  a@b.com  ');
    await fireEvent.press(screen.getByRole('button', { name: 'Password dimenticata?' }));

    await waitFor(() => expect(mockedForgotPassword).toHaveBeenCalledWith('a@b.com'));
    // Same answer whether or not the address has an account: the screen
    // must not let anyone probe for registered emails.
    expect(
      screen.getByText(
        'Se esiste un account con questa email, ti arriveranno le istruzioni per cambiare la password.',
      ),
    ).toBeTruthy();
  });
});
