import { Pressable, TextInput, View } from 'react-native';
import { Icon } from './Icon';
import { colors, HIT_SIZE, radius, space } from './tokens';

type Props = {
  value: string;
  onChangeText: (value: string) => void;
  /** Accessible name for the input; a search field has no visible label. */
  label: string;
  placeholder?: string;
  /** Accessible name for the clear button, shown once there is text to clear. */
  clearLabel: string;
};

/**
 * The rounded grey search box: a magnifier, the text, and a clear button
 * once there is something to clear. Not a `Field` — it has no visible
 * label and no domain meaning beyond "here is some typed text".
 */
export function SearchField({ value, onChangeText, label, placeholder, clearLabel }: Props) {
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.sm,
        minHeight: HIT_SIZE,
        paddingHorizontal: space.md,
        backgroundColor: colors.fill,
        borderRadius: radius.control,
      }}
    >
      <Icon name="search" size={18} color={colors.textTertiary} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textTertiary}
        accessibilityLabel={label}
        autoCapitalize="none"
        autoCorrect={false}
        style={{ flex: 1, fontSize: 17, color: colors.text, paddingVertical: space.sm }}
      />
      {value.length > 0 ? (
        <Pressable role="button" accessibilityLabel={clearLabel} onPress={() => onChangeText('')} hitSlop={8}>
          <Icon name="close" size={18} color={colors.textTertiary} />
        </Pressable>
      ) : null}
    </View>
  );
}
