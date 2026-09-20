import { TextInput, View, type TextInputProps } from 'react-native';
import { Text } from './Text';
import { colors, space, HIT_SIZE } from './tokens';

type Props = TextInputProps & { label: string; error?: string };

export function Field({ label, error, style, ...rest }: Props) {
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
        accessibilityLabel={label}
        aria-labelledby={`label-${label}`}
        placeholderTextColor={colors.textTertiary}
        {...rest}
        style={[
          { flex: 1, fontSize: 17, color: error ? colors.redText : colors.text, paddingVertical: 12 },
          style,
        ]}
      />
    </View>
  );
}
