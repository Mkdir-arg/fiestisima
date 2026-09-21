import { render, screen, fireEvent, cleanup } from '@testing-library/react-native';
import { Text as RNText } from 'react-native';
import { Sheet } from './Sheet';

afterEach(cleanup);

describe('Sheet', () => {
  it('renders nothing while not visible', async () => {
    const { toJSON } = await render(
      <Sheet visible={false} onClose={() => {}} closeLabel="Chiudi">
        <RNText>Contenuto</RNText>
      </Sheet>,
    );
    expect(toJSON()).toBeNull();
  });

  it('renders the title and children while visible', async () => {
    await render(
      <Sheet visible onClose={() => {}} closeLabel="Chiudi" title="Unità">
        <RNText>Contenuto</RNText>
      </Sheet>,
    );
    expect(screen.getByText('Unità')).toBeOnTheScreen();
    expect(screen.getByText('Contenuto')).toBeOnTheScreen();
  });

  it('calls onClose when the backdrop is pressed', async () => {
    const onClose = jest.fn();
    await render(
      <Sheet visible onClose={onClose} closeLabel="Chiudi">
        <RNText>Contenuto</RNText>
      </Sheet>,
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Chiudi' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not call onClose when the sheet content itself is pressed', async () => {
    const onClose = jest.fn();
    await render(
      <Sheet visible onClose={onClose} closeLabel="Chiudi">
        <RNText>Contenuto</RNText>
      </Sheet>,
    );
    await fireEvent.press(screen.getByTestId('sheet-content'));
    expect(onClose).not.toHaveBeenCalled();
  });
});
