import { render, screen, cleanup } from '@testing-library/react-native';
import TabsLayout from '@/app/(app)/(tabs)/_layout';
import { useLayout } from '@/src/ui/useLayout';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

afterEach(cleanup);

// `Tabs`/`Tabs.Screen` are the real navigator: rendering them needs a full
// navigation container this test does not set up. Stubbed here to a plain
// wrapper that records which routes were registered, which is what this
// layout is actually responsible for getting right (order, names, icons).
const registeredScreens: { name: string; title?: string }[] = [];
jest.mock('expo-router', () => {
  const react = require('react');
  const { View: RNView } = require('react-native');
  const Tabs: any = ({ children }: { children: React.ReactNode }) =>
    react.createElement(RNView, null, children);
  Tabs.Screen = ({ name, options }: { name: string; options?: { title?: string } }) => {
    registeredScreens.push({ name, title: options?.title });
    return null;
  };
  return {
    Tabs,
    Link: ({ children }: { children: React.ReactNode }) => children,
    usePathname: jest.fn(() => '/(app)/(tabs)/prodotti'),
  };
});

jest.mock('@/src/ui/useLayout', () => ({
  useLayout: jest.fn(),
}));

jest.mock('@/src/features/auth/SessionProvider', () => ({
  useSessionContext: jest.fn(),
}));

const mockedUseLayout = useLayout as unknown as jest.Mock;
const mockedUseSessionContext = useSessionContext as unknown as jest.Mock;

describe('TabsLayout', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    registeredScreens.length = 0;
    mockedUseSessionContext.mockReturnValue({
      profile: {
        full_name: 'Maria Rossi',
        role: 'titolare',
        business: { name: 'Il Giardino' },
      },
    });
  });

  it('registers oggi first, then prodotti, scadenze, altro, on every layout', async () => {
    mockedUseLayout.mockReturnValue({ isWide: false });
    await render(<TabsLayout />);
    expect(registeredScreens.map((s) => s.name)).toEqual(['oggi', 'prodotti', 'scadenze', 'altro']);
  });

  it('shows a sidebar with the business name and nav items, but not Altro as one of them, on a wide screen', async () => {
    mockedUseLayout.mockReturnValue({ isWide: true });
    await render(<TabsLayout />);

    expect(screen.getByText('Il Giardino')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Oggi' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Prodotti' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Scadenze' })).toBeTruthy();
    // "Altro" is reached through the profile row instead, not a separate
    // nav item: exactly one "Altro"-labelled button (the footer row).
    expect(screen.getAllByRole('button', { name: 'Altro' })).toHaveLength(1);
  });

  it('shows the signed-in person and role in a footer row that opens Altro', async () => {
    mockedUseLayout.mockReturnValue({ isWide: true });
    await render(<TabsLayout />);

    expect(screen.getByText('Maria Rossi')).toBeOnTheScreen();
    expect(screen.getByText('Titolare')).toBeOnTheScreen();
  });

  it('does not render a sidebar on a narrow screen', async () => {
    mockedUseLayout.mockReturnValue({ isWide: false });
    await render(<TabsLayout />);

    expect(screen.queryByText('Il Giardino')).toBeNull();
  });
});
