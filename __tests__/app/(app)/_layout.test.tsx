import { render, screen, cleanup } from '@testing-library/react-native';
import AppLayout from '@/app/(app)/_layout';
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

describe('AppLayout', () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders nothing while the session is loading', async () => {
    mockedUseSessionContext.mockReturnValue({ session: null, isLoading: true });
    const { toJSON } = await render(<AppLayout />);
    expect(toJSON()).toBeNull();
  });

  it('redirects to sign-in when there is no session', async () => {
    mockedUseSessionContext.mockReturnValue({ session: null, isLoading: false });
    await render(<AppLayout />);
    expect(screen.getByText('redirect:/(auth)/accedi')).toBeTruthy();
  });

  it('renders the app stack when signed in', async () => {
    mockedUseSessionContext.mockReturnValue({ session: { accessToken: 'x' }, isLoading: false });
    await render(<AppLayout />);
    expect(screen.queryByText(/redirect:/)).toBeNull();
  });
});
