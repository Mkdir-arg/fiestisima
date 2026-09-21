import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react-native';
import ResetPasswordScreen from '@/app/(auth)/reset-password/[token]';
import { resetPassword } from '@/src/features/auth/api';

afterEach(cleanup);

jest.mock('expo-router', () => ({
  router: { replace: jest.fn(), push: jest.fn(), back: jest.fn() },
  useLocalSearchParams: () => ({ token: 'tok-1' }),
}));

jest.mock('@/src/features/auth/api', () => ({
  resetPassword: jest.fn(),
}));

const mockedResetPassword = resetPassword as unknown as jest.Mock;

async function fill(password: string, repeat: string) {
  await fireEvent.changeText(screen.getByLabelText('Nuova password'), password);
  await fireEvent.changeText(screen.getByLabelText('Ripeti'), repeat);
  await fireEvent.press(screen.getByRole('button', { name: 'Salva la password' }));
}

describe('ResetPasswordScreen', () => {
  beforeEach(() => jest.clearAllMocks());

  it('refuses a password shorter than the API would accept', async () => {
    await render(<ResetPasswordScreen />);
    await fill('short7', 'short7');

    // Caught here rather than by a 422 round trip.
    expect(mockedResetPassword).not.toHaveBeenCalled();
    expect(screen.getByText('La password deve avere almeno 8 caratteri.')).toBeTruthy();
  });

  it('refuses two passwords that do not match', async () => {
    await render(<ResetPasswordScreen />);
    await fill('longenough1', 'longenough2');

    expect(mockedResetPassword).not.toHaveBeenCalled();
    expect(screen.getByText('Le due password non coincidono.')).toBeTruthy();
  });

  it('sends the token with the new password and confirms', async () => {
    mockedResetPassword.mockResolvedValue({ ok: true });
    await render(<ResetPasswordScreen />);
    await fill('longenough1', 'longenough1');

    await waitFor(() => expect(mockedResetPassword).toHaveBeenCalledWith('tok-1', 'longenough1'));
    expect(screen.getByText('Password aggiornata. Ora puoi accedere.')).toBeTruthy();
    // The form is gone: there is nothing left to submit.
    expect(screen.queryByLabelText('Nuova password')).toBeNull();
  });

  it('shows the message from a dead or spent link', async () => {
    mockedResetPassword.mockResolvedValue({ ok: false, message: 'Il link non è valido o è scaduto.' });
    await render(<ResetPasswordScreen />);
    await fill('longenough1', 'longenough1');

    await waitFor(() => expect(screen.getByText('Il link non è valido o è scaduto.')).toBeTruthy());
    expect(screen.getByLabelText('Nuova password')).toBeTruthy();
  });
});
