import { render, screen, fireEvent, cleanup } from '@testing-library/react-native';
import { SegmentedControl } from './SegmentedControl';

afterEach(cleanup);

const OPTIONS = [
  { value: 'tutti', label: 'Tutti' },
  { value: 'scadenza', label: 'In scadenza' },
  { value: 'scaduti', label: 'Scaduti' },
] as const;

describe('SegmentedControl', () => {
  it('renders every option', async () => {
    await render(<SegmentedControl options={OPTIONS} value="tutti" onChange={() => {}} />);
    expect(screen.getByText('Tutti')).toBeOnTheScreen();
    expect(screen.getByText('In scadenza')).toBeOnTheScreen();
    expect(screen.getByText('Scaduti')).toBeOnTheScreen();
  });

  it('marks the current value as selected', async () => {
    await render(<SegmentedControl options={OPTIONS} value="scadenza" onChange={() => {}} />);
    expect(screen.getByRole('radio', { name: 'In scadenza' })).toHaveProp('accessibilityState', {
      selected: true,
    });
    expect(screen.getByRole('radio', { name: 'Tutti' })).toHaveProp('accessibilityState', {
      selected: false,
    });
  });

  it('calls onChange with the pressed option value', async () => {
    const onChange = jest.fn();
    await render(<SegmentedControl options={OPTIONS} value="tutti" onChange={onChange} />);
    await fireEvent.press(screen.getByRole('radio', { name: 'Scaduti' }));
    expect(onChange).toHaveBeenCalledWith('scaduti');
  });
});
