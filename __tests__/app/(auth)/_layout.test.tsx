import { render, screen, cleanup } from '@testing-library/react-native';
import AuthLayout from '@/app/(auth)/_layout';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

afterEach(cleanup);

jest.mock('expo-router', () => {
  const { Text } = require('react-native');
  return {
    Stack: () => null,
    Redirect: ({ href }: { href: string }) => <Text>{`redirect:${href}`}</Text>,
  };
});

jest.mock('@/src/features/auth/SessionProvider', () => ({
  useSessionContext: jest.fn(),
}));

const mockedUseSessionContext = useSessionContext as unknown as jest.Mock;

describe('AuthLayout', () => {
  beforeEach(() => jest.clearAllMocks());

  it('redirects to the product list when session and profile are both present', async () => {
    mockedUseSessionContext.mockReturnValue({ session: { accessToken: 'x' }, profile: { role: 'titolare' } });
    await render(<AuthLayout />);
    expect(screen.getByText('redirect:/(app)/(tabs)/prodotti')).toBeTruthy();
  });

  it('renders the auth stack when there is no session', async () => {
    mockedUseSessionContext.mockReturnValue({ session: null, profile: null });
    await render(<AuthLayout />);
    expect(screen.queryByText(/redirect:/)).toBeNull();
  });
});
