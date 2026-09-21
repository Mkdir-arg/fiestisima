import { View } from 'react-native';
import { Text } from './Text';
import { colors, radius, space } from './tokens';

type Tone = 'neutral' | 'blue' | 'red' | 'amber';

type Props = { label: string; tone?: Tone };

const BACKGROUNDS: Record<Tone, string> = {
  neutral: colors.fill,
  blue: colors.blueTint,
  red: colors.redTint,
  amber: colors.amberTint,
};

/** A small pill for a count or a role, inline with other text — smaller and
 * quieter than `StatusPill`, which always means "time is running out". */
export function Badge({ label, tone = 'neutral' }: Props) {
  return (
    <View
      testID="badge"
      style={{
        alignSelf: 'flex-start',
        backgroundColor: BACKGROUNDS[tone],
        borderRadius: radius.pill,
        paddingHorizontal: space.sm,
        paddingVertical: 3,
      }}
    >
      <Text variant="caption" tone={tone === 'neutral' ? 'secondary' : tone} style={{ fontWeight: '600' }}>
        {label}
      </Text>
    </View>
  );
}
