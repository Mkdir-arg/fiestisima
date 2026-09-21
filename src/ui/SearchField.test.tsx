import { render, screen, fireEvent, cleanup } from '@testing-library/react-native';
import { SearchField } from './SearchField';

afterEach(cleanup);

describe('SearchField', () => {
  it('calls onChangeText as the user types', async () => {
    const onChangeText = jest.fn();
    await render(
      <SearchField value="" onChangeText={onChangeText} label="Cerca" clearLabel="Cancella la ricerca" />,
    );
    await fireEvent.changeText(screen.getByLabelText('Cerca'), 'farina');
    expect(onChangeText).toHaveBeenCalledWith('farina');
  });

  it('shows no clear button when empty', async () => {
    await render(<SearchField value="" onChangeText={() => {}} label="Cerca" clearLabel="Cancella la ricerca" />);
    expect(screen.queryByRole('button', { name: 'Cancella la ricerca' })).toBeNull();
  });

  it('clears the text when the clear button is pressed', async () => {
    const onChangeText = jest.fn();
    await render(
      <SearchField value="farina" onChangeText={onChangeText} label="Cerca" clearLabel="Cancella la ricerca" />,
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Cancella la ricerca' }));
    expect(onChangeText).toHaveBeenCalledWith('');
  });
});
