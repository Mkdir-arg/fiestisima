import { render, screen, cleanup } from '@testing-library/react-native';
import AuthLayout from '@/app/(auth)/_layout';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

afterEach(cleanup);

jest.mock('expo-router', () => {
  const { Text } = require('react-native');
  return {
    Stack: () => <Text>auth-stack</Text>,
    Redirect: ({ href }: { href: string }) => <Text>{`redirect:${href}`}</Text>,
  };
});

jest.mock('@/src/features/auth/SessionProvider', () => ({
  useSessionContext: jest.fn(),
}));

const mockedUseSessionContext = useSessionContext as unknown as jest.Mock;

describe('AuthLayout', () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders nothing at all while the session is still loading', async () => {
    // The point of the guard: someone already signed in who opens
    // /accedi directly must not see the login form for the one round
    // trip it takes /auth/me to answer.
    mockedUseSessionContext.mockReturnValue({ session: { accessToken: 'x' }, profile: null, isLoading: true });
    await render(<AuthLayout />);
    expect(screen.queryByText(/redirect:/)).toBeNull();
    // Not just "no redirect": the login form must not be on screen either.
    expect(screen.queryByText('auth-stack')).toBeNull();
  });

  it('redirects to the product list when session and profile are both present', async () => {
    mockedUseSessionContext.mockReturnValue({ session: { accessToken: 'x' }, profile: { role: 'titolare' }, isLoading: false });
    await render(<AuthLayout />);
    expect(screen.getByText('redirect:/(app)/(tabs)/prodotti')).toBeTruthy();
  });

  it('renders the auth stack when there is no session', async () => {
    mockedUseSessionContext.mockReturnValue({ session: null, profile: null, isLoading: false });
    await render(<AuthLayout />);
    expect(screen.queryByText(/redirect:/)).toBeNull();
    expect(screen.getByText('auth-stack')).toBeTruthy();
  });
});
