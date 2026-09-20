import { render, screen } from '@testing-library/react-native';
import { StatusPill } from './StatusPill';
import { colors } from './tokens';

// `render` is async in @testing-library/react-native 14 (it awaits `act()`
// internally to flush effects), so every test here must be async and await it
// before querying `screen` — otherwise `screen` still points at the
// not-yet-rendered placeholder and every query throws "render function has
// not been called".
describe('StatusPill', () => {
  it('shows the remaining days in plural', async () => {
    await render(<StatusPill daysLeft={5} />);
    expect(screen.getByText('5 giorni')).toBeOnTheScreen();
  });

  it('shows the singular with one day', async () => {
    await render(<StatusPill daysLeft={1} />);
    expect(screen.getByText('1 giorno')).toBeOnTheScreen();
  });

  it('says oggi when it expires today', async () => {
    await render(<StatusPill daysLeft={0} />);
    expect(screen.getByText('oggi')).toBeOnTheScreen();
  });

  it('counts backwards when already expired', async () => {
    await render(<StatusPill daysLeft={-3} />);
    expect(screen.getByText('3 gg fa')).toBeOnTheScreen();
  });

  it('uses red when expired', async () => {
    await render(<StatusPill daysLeft={-1} />);
    expect(screen.getByTestId('status-pill')).toHaveStyle({ backgroundColor: colors.redTint });
  });

  it('uses amber within the threshold', async () => {
    await render(<StatusPill daysLeft={4} thresholdDays={7} />);
    expect(screen.getByTestId('status-pill')).toHaveStyle({ backgroundColor: colors.amberTint });
  });

  it('uses grey outside the threshold: what is fine gets no color', async () => {
    await render(<StatusPill daysLeft={30} thresholdDays={7} />);
    expect(screen.getByTestId('status-pill')).toHaveStyle({ backgroundColor: colors.fill });
  });
});
