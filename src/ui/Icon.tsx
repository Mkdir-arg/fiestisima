import { Ionicons } from '@expo/vector-icons';
import type { ColorValue } from 'react-native';
import { colors } from './tokens';

/**
 * Every icon in the app is drawn through this map rather than importing
 * `Ionicons` (or any other vendor package) directly anywhere else, so the
 * whole set can be swapped by editing this one file. Outline glyphs, to
 * match the iOS-native language the rest of `src/ui/` follows.
 */
const GLYPHS = {
  today: 'today-outline',
  products: 'cube-outline',
  expiry: 'time-outline',
  more: 'ellipsis-horizontal-circle-outline',
  add: 'add',
  search: 'search-outline',
  close: 'close-circle',
  person: 'person-circle-outline',
} as const;

export type IconName = keyof typeof GLYPHS;

type Props = {
  name: IconName;
  size?: number;
  // `ColorValue` (not just `string`) so a colour handed through from a
  // react-navigation render prop — e.g. a tab bar's active/inactive tint —
  // is accepted without a cast.
  color?: ColorValue;
};

export function Icon({ name, size = 22, color = colors.text }: Props) {
  return (
    <Ionicons
      name={GLYPHS[name]}
      size={size}
      color={color}
      // Decorative by default: whatever wraps it (a row, a labelled
      // button) already carries the accessible name.
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    />
  );
}
