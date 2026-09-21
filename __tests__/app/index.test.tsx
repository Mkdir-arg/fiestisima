import { render, screen, cleanup } from '@testing-library/react-native';
import Index from '@/app/index';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

afterEach(cleanup);

jest.mock('expo-router', () => {
  const { Text } = require('react-native');
  return {
    Redirect: ({ href }: { href: string }) => <Text>{`redirect:${href}`}</Text>,
  };
});

jest.mock('@/src/features/auth/SessionProvider', () => ({
  useSessionContext: jest.fn(),
}));

const mockedUseSessionContext = useSessionContext as unknown as jest.Mock;

describe('Index', () => {
  beforeEach(() => jest.clearAllMocks());

  it('shows a spinner while loading, with no redirect yet', async () => {
    mockedUseSessionContext.mockReturnValue({ session: null, profile: null, isLoading: true });
    await render(<Index />);
    expect(screen.queryByText(/redirect:/)).toBeNull();
  });

  it('redirects to the product list when signed in', async () => {
    mockedUseSessionContext.mockReturnValue({
      session: { accessToken: 'x' },
      profile: { role: 'titolare' },
      isLoading: false,
    });
    await render(<Index />);
    expect(screen.getByText('redirect:/(app)/(tabs)/prodotti')).toBeTruthy();
  });

  it('redirects to sign-in when signed out', async () => {
    mockedUseSessionContext.mockReturnValue({ session: null, profile: null, isLoading: false });
    await render(<Index />);
    expect(screen.getByText('redirect:/(auth)/accedi')).toBeTruthy();
  });
});
