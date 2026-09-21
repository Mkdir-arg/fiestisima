import { render, screen, fireEvent, cleanup } from '@testing-library/react-native';
import { EmptyState } from './EmptyState';

afterEach(cleanup);

describe('EmptyState', () => {
  it('shows the title and message', async () => {
    await render(<EmptyState icon="products" title="Nessun prodotto" message="Aggiungi il primo." />);
    expect(screen.getByText('Nessun prodotto')).toBeOnTheScreen();
    expect(screen.getByText('Aggiungi il primo.')).toBeOnTheScreen();
  });

  it('renders no action when none is given', async () => {
    await render(<EmptyState icon="expiry" title="Presto disponibile" />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('calls onAction when the action button is pressed', async () => {
    const onAction = jest.fn();
    await render(
      <EmptyState icon="products" title="Nessun prodotto" actionLabel="Aggiungi il primo" onAction={onAction} />,
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Aggiungi il primo' }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it('does not render an action if only the label is given, without a handler', async () => {
    await render(<EmptyState icon="products" title="Nessun prodotto" actionLabel="Aggiungi il primo" />);
    expect(screen.queryByRole('button')).toBeNull();
  });
});
