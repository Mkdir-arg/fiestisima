import { render, screen, fireEvent } from '@testing-library/react-native';
import { Button } from './Button';
import { HIT_SIZE } from './tokens';

// `render` and `fireEvent` are async in @testing-library/react-native 14
// (see StatusPill.test.tsx for why), so both are awaited here.
describe('Button', () => {
  it('calls onPress when tapped', async () => {
    const onPress = jest.fn();
    await render(<Button title="Salva" onPress={onPress} />);
    await fireEvent.press(screen.getByRole('button', { name: 'Salva' }));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('does not call onPress when disabled', async () => {
    const onPress = jest.fn();
    await render(<Button title="Salva" onPress={onPress} disabled />);
    await fireEvent.press(screen.getByRole('button', { name: 'Salva' }));
    expect(onPress).not.toHaveBeenCalled();
  });

  it('respects the minimum touch height', async () => {
    await render(<Button title="Salva" onPress={() => {}} />);
    expect(screen.getByRole('button', { name: 'Salva' })).toHaveStyle({ minHeight: HIT_SIZE });
  });
});
