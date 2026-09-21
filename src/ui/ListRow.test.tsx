import { render, screen, cleanup } from '@testing-library/react-native';
import { ListRow } from './ListRow';
import { colors } from './tokens';

afterEach(cleanup);

describe('ListRow', () => {
  it('colours the title red for a destructive row', async () => {
    await render(<ListRow title="Esci" onPress={() => {}} tone="destructive" />);
    expect(screen.getByText('Esci')).toHaveStyle({ color: colors.redText });
  });

  it('keeps the default colour otherwise', async () => {
    await render(<ListRow title="Prodotti" onPress={() => {}} />);
    expect(screen.getByText('Prodotti')).toHaveStyle({ color: colors.text });
  });

  it('hides the chevron when showChevron is false', async () => {
    const { queryByTestId } = await render(
      <ListRow title="Esci" onPress={() => {}} showChevron={false} />,
    );
    expect(queryByTestId('chevron')).toBeNull();
  });
});
