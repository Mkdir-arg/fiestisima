import { Pressable, View } from 'react-native';
import { Text } from './Text';
import { colors, HIT_SIZE, radius } from './tokens';

type Option<T extends string> = { value: T; label: string };

type Props<T extends string> = {
  options: readonly Option<T>[];
  value: T;
  onChange: (value: T) => void;
};

/**
 * The iOS segmented control: a small, fixed set of mutually exclusive
 * choices shown side by side rather than as rows to tap through — Tutti /
 * In scadenza / Scaduti, a unit, a storage place. Generic over the option
 * values so the caller keeps its own literal union, not a string.
 */
export function SegmentedControl<T extends string>({ options, value, onChange }: Props<T>) {
  return (
    <View
      style={{
        flexDirection: 'row',
        backgroundColor: colors.fill,
        borderRadius: radius.control,
        padding: 2,
      }}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            role="radio"
            accessibilityLabel={option.label}
            accessibilityState={{ selected }}
            onPress={() => onChange(option.value)}
            style={{
              flex: 1,
              minHeight: HIT_SIZE - 8,
              borderRadius: radius.control - 2,
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: selected ? colors.surface : 'transparent',
            }}
          >
            <Text
              variant="subhead"
              tone={selected ? 'primary' : 'secondary'}
              style={{ fontWeight: selected ? '600' : '400' }}
            >
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
