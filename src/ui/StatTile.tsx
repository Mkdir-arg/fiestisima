import { View, type ViewStyle } from 'react-native';
import { Text } from './Text';
import { colors, radius, space } from './tokens';

type Tone = 'neutral' | 'red' | 'amber';

type Props = {
  value: string;
  label: string;
  caption?: string;
  tone?: Tone;
  style?: ViewStyle;
};

const VALUE_TONES = {
  neutral: 'primary',
  red: 'red',
  amber: 'amber',
} as const;

/**
 * One number on a card, for a dashboard row. No domain knowledge: the
 * caller decides what the number means, whether it needs a tone, and
 * whether a caption is needed (e.g. a placeholder still waiting on data).
 */
export function StatTile({ value, label, caption, tone = 'neutral', style }: Props) {
  return (
    <View
      testID="stat-tile"
      style={[
        {
          flexGrow: 1,
          flexBasis: 150,
          backgroundColor: colors.surface,
          borderRadius: radius.card,
          padding: space.lg,
          minHeight: 104,
          justifyContent: 'space-between',
        },
        style,
      ]}
    >
      <Text variant="largeTitle" tone={VALUE_TONES[tone]}>
        {value}
      </Text>
      <View>
        <Text variant="subhead" tone="secondary">
          {label}
        </Text>
        {caption ? (
          <Text variant="caption" tone="tertiary" style={{ marginTop: 2 }}>
            {caption}
          </Text>
        ) : null}
      </View>
    </View>
  );
}
