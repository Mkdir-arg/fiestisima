import { render } from '@testing-library/react-native';
import { Icon, type IconName } from './Icon';

// One icon per test, not a loop: the underlying `@expo/vector-icons` class
// component loads its font asynchronously in `componentDidMount` outside of
// React's effect system, and rendering several instances back-to-back in a
// single test trips React's "overlapping act() calls" warning.
const NAMES: IconName[] = ['today', 'products', 'expiry', 'more', 'add', 'search', 'close', 'person'];

describe('Icon', () => {
  it.each(NAMES)('renders "%s" without crashing', async (name) => {
    const { toJSON } = await render(<Icon name={name} />);
    expect(toJSON()).not.toBeNull();
  });

  it('is hidden from the accessibility tree, since it is always decorative here', async () => {
    const { toJSON } = await render(<Icon name="search" />);
    expect(toJSON()?.props.accessibilityElementsHidden).toBe(true);
  });
});
