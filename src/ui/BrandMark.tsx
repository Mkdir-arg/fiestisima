import { View } from 'react-native';
import { Text } from './Text';
import { colors } from './tokens';

type Props = { size?: number };

/**
 * The app icon, drawn rather than shipped as an image: the same blue
 * square with an F that public/icon-512.png carries, so the sign-in
 * screen and the icon on the home screen are recognisably one thing.
 */
export function BrandMark({ size = 64 }: Props) {
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{
        width: size,
        height: size,
        // iOS' own icon curvature, near enough: a little under a quarter
        // of the side.
        borderRadius: size * 0.225,
        backgroundColor: colors.blue,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Text
        style={{
          fontSize: size * 0.58,
          lineHeight: size * 0.72,
          fontWeight: '700',
          color: colors.surface,
        }}
      >
        F
      </Text>
    </View>
  );
}
