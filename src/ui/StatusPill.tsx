import { View } from 'react-native';
import { Text } from './Text';
import { colors, radius } from './tokens';

type Props = { daysLeft: number; thresholdDays?: number };

// Italian labels composed here on purpose: `giorni` / `giorno` / `oggi` / `gg fa`
// are grammar (plural/singular/today/past), not a translatable UI string.
function label(daysLeft: number): string {
  if (daysLeft < 0) return `${Math.abs(daysLeft)} gg fa`;
  if (daysLeft === 0) return 'oggi';
  if (daysLeft === 1) return '1 giorno';
  return `${daysLeft} giorni`;
}

export function StatusPill({ daysLeft, thresholdDays = 7 }: Props) {
  const variant =
    daysLeft < 0 ? 'red' : daysLeft <= thresholdDays ? 'amber' : 'neutral';

  const background =
    variant === 'red' ? colors.redTint : variant === 'amber' ? colors.amberTint : colors.fill;
  const tone = variant === 'red' ? 'red' : variant === 'amber' ? 'amber' : 'secondary';

  return (
    <View
      testID="status-pill"
      style={{
        backgroundColor: background,
        borderRadius: radius.pill,
        paddingHorizontal: 9,
        paddingVertical: 4,
      }}
    >
      <Text variant="footnote" tone={tone} style={{ fontWeight: '600' }}>
        {label(daysLeft)}
      </Text>
    </View>
  );
}
