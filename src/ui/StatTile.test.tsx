import { render, screen, cleanup } from '@testing-library/react-native';
import { StatTile } from './StatTile';
import { colors } from './tokens';

afterEach(cleanup);

describe('StatTile', () => {
  it('shows the value and label', async () => {
    await render(<StatTile value="12" label="Prodotti a catalogo" />);
    expect(screen.getByText('12')).toBeOnTheScreen();
    expect(screen.getByText('Prodotti a catalogo')).toBeOnTheScreen();
  });

  it('shows a placeholder value with its caption', async () => {
    await render(<StatTile value="—" label="In scadenza" caption="Arriva col Blocco A" />);
    expect(screen.getByText('—')).toBeOnTheScreen();
    expect(screen.getByText('Arriva col Blocco A')).toBeOnTheScreen();
  });

  it('has no caption by default', async () => {
    await render(<StatTile value="3" label="Sotto scorta" />);
    expect(screen.queryByText('Arriva col Blocco A')).toBeNull();
  });

  it('colours the value red when the tone is red', async () => {
    await render(<StatTile value="2" label="Scaduti" tone="red" />);
    expect(screen.getByText('2')).toHaveStyle({ color: colors.redText });
  });

  it('defaults to no colour: what is fine gets no tone', async () => {
    await render(<StatTile value="12" label="Prodotti a catalogo" />);
    expect(screen.getByText('12')).toHaveStyle({ color: colors.text });
  });
});
