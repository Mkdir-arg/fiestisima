import { Pressable, ActivityIndicator, View } from 'react-native';
import { Text } from './Text';
import { colors, radius, HIT_SIZE } from './tokens';

type Props = {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'destructive';
  disabled?: boolean;
  loading?: boolean;
};

export function Button({
  title,
  onPress,
  variant = 'primary',
  disabled = false,
  loading = false,
}: Props) {
  const background =
    variant === 'primary' ? colors.blue : variant === 'destructive' ? colors.redTint : colors.fill;
  const tone = variant === 'primary' ? 'primary' : variant === 'destructive' ? 'red' : 'blue';
  const textColor = variant === 'primary' ? colors.surface : undefined;

  return (
    <Pressable
      role="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: disabled || loading }}
      disabled={disabled || loading}
      onPress={onPress}
      style={{
        minHeight: HIT_SIZE,
        paddingHorizontal: 22,
        borderRadius: radius.card,
        backgroundColor: background,
        opacity: disabled ? 0.4 : 1,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'primary' ? colors.surface : colors.blue} />
      ) : (
        <Text variant="headline" tone={tone} style={textColor ? { color: textColor } : undefined}>
          {title}
        </Text>
      )}
    </Pressable>
  );
}
