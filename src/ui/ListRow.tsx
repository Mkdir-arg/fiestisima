import type { ReactNode } from 'react';
import { Pressable, View } from 'react-native';
import { Text } from './Text';
import { colors, space, HIT_SIZE } from './tokens';

type Props = {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  onPress?: () => void;
  /** `destructive` colours the title red, for a row like "Esci". */
  tone?: 'default' | 'destructive';
  /** Set to `false` to suppress the chevron on a pressable row that is an
   * action rather than navigation (again, "Esci"). Defaults to `true`. */
  showChevron?: boolean;
};

export function ListRow({ title, subtitle, right, onPress, tone = 'default', showChevron = true }: Props) {
  const content = (
    <View
      style={{
        minHeight: HIT_SIZE + 10,
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.md,
        paddingHorizontal: space.lg,
        paddingVertical: 11,
      }}
    >
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text variant="body" tone={tone === 'destructive' ? 'red' : 'primary'} style={{ fontWeight: '500' }}>
          {title}
        </Text>
        {subtitle ? (
          <Text variant="subhead" tone="secondary" style={{ marginTop: 2 }}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {right}
      {onPress && showChevron ? <Chevron /> : null}
    </View>
  );

  if (!onPress) return content;
  return (
    <Pressable role="button" accessibilityLabel={title} onPress={onPress}>
      {content}
    </Pressable>
  );
}

function Chevron() {
  return (
    <View
      testID="chevron"
      style={{
        width: 8,
        height: 13,
        borderRightWidth: 2,
        borderTopWidth: 2,
        borderColor: colors.chevron,
        transform: [{ rotate: '45deg' }],
      }}
    />
  );
}
