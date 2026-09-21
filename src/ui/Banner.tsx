import { View } from 'react-native';
import { Text } from './Text';
import { colors, radius, space } from './tokens';

type Tone = 'red' | 'amber' | 'blue';

type Props = { tone: Tone; children: string };

const tints: Record<Tone, string> = {
  red: colors.redTint,
  amber: colors.amberTint,
  blue: colors.blueTint,
};

/**
 * A tinted message block. Loud enough to be read at a glance across a
 * kitchen, which a line of red footnote text is not.
 *
 * `blue` is the confirmation tone on purpose: the visual system has no
 * green, so "it worked" and "here is what happens next" share the accent
 * colour rather than inventing one.
 */
export function Banner({ tone, children }: Props) {
  return (
    <View
      // Announced by screen readers as soon as it appears, which matters
      // because it usually replaces something the person just tried.
      role="alert"
      style={{
        backgroundColor: tints[tone],
        borderRadius: radius.card,
        paddingVertical: space.md,
        paddingHorizontal: space.lg,
        marginBottom: space.lg,
      }}
    >
      <Text variant="subhead" tone={tone}>
        {children}
      </Text>
    </View>
  );
}
