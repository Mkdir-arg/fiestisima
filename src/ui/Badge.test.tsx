import { render, screen, cleanup } from '@testing-library/react-native';
import { Badge } from './Badge';
import { colors } from './tokens';

afterEach(cleanup);

describe('Badge', () => {
  it('shows the label', async () => {
    await render(<Badge label="Titolare" />);
    expect(screen.getByText('Titolare')).toBeOnTheScreen();
  });

  it('defaults to the neutral tone', async () => {
    await render(<Badge label="3" />);
    expect(screen.getByTestId('badge')).toHaveStyle({ backgroundColor: colors.fill });
  });

  it('uses the blue tint for the blue tone', async () => {
    await render(<Badge label="Titolare" tone="blue" />);
    expect(screen.getByTestId('badge')).toHaveStyle({ backgroundColor: colors.blueTint });
  });
});
