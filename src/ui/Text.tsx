import { Text as RNText, type TextProps as RNTextProps } from 'react-native';
import { colors, type, type TypeVariant } from './tokens';

type Props = RNTextProps & {
  variant?: TypeVariant;
  tone?: 'primary' | 'secondary' | 'tertiary' | 'blue' | 'red' | 'amber';
};

const tones = {
  primary: colors.text,
  secondary: colors.textSecondary,
  tertiary: colors.textTertiary,
  blue: colors.blue,
  red: colors.redText,
  amber: colors.amberText,
} as const;

export function Text({ variant = 'body', tone = 'primary', style, ...rest }: Props) {
  return <RNText {...rest} style={[type[variant], { color: tones[tone] }, style]} />;
}
