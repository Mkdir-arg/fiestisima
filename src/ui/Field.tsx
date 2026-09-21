import type { ReactNode, Ref } from 'react';
import { TextInput, View, type TextInputProps } from 'react-native';
import { Text } from './Text';
import { colors, space, HIT_SIZE } from './tokens';

type Props = TextInputProps & {
  label: string;
  /** Trailing accessory inside the row, e.g. a show/hide password toggle. */
  right?: ReactNode;
  /**
   * Forwarded to the input itself, so one field can move focus to the
   * next. Declared explicitly because React 19 passes `ref` as an
   * ordinary prop, and TextInputProps does not carry it.
   */
  ref?: Ref<TextInput>;
};

export function Field({ label, style, right, ref, ...rest }: Props) {
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.md,
        paddingHorizontal: space.lg,
        minHeight: HIT_SIZE + 8,
      }}
    >
      <Text variant="body" style={{ width: 110 }} nativeID={`label-${label}`}>
        {label}
      </Text>
      <TextInput
        ref={ref}
        accessibilityLabel={label}
        aria-labelledby={`label-${label}`}
        placeholderTextColor={colors.textTertiary}
        {...rest}
        style={[
          { flex: 1, fontSize: 17, color: colors.text, paddingVertical: 12 },
          style,
        ]}
      />
      {right}
    </View>
  );
}
