import { render, screen, cleanup } from '@testing-library/react-native';
import { Text as RNText } from 'react-native';
import { Card } from './Card';

afterEach(cleanup);

describe('Card', () => {
  it('renders its children', async () => {
    await render(
      <Card>
        <RNText>Corpo della card</RNText>
      </Card>,
    );
    expect(screen.getByText('Corpo della card')).toBeOnTheScreen();
  });

  it('renders an optional header and footer', async () => {
    await render(
      <Card header={<RNText>Intestazione</RNText>} footer={<RNText>Nota a piè</RNText>}>
        <RNText>Corpo</RNText>
      </Card>,
    );
    expect(screen.getByText('Intestazione')).toBeOnTheScreen();
    expect(screen.getByText('Corpo')).toBeOnTheScreen();
    expect(screen.getByText('Nota a piè')).toBeOnTheScreen();
  });
});
