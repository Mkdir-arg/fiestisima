import type { ReactNode } from 'react';
import { View, type ViewStyle } from 'react-native';
import { colors, radius, space } from './tokens';

type Props = {
  children: ReactNode;
  header?: ReactNode;
  footer?: ReactNode;
  style?: ViewStyle;
};

/**
 * A white surface for content that is not a list of rows: a stat, a
 * profile summary, a form section. `ListGroup` is for rows with
 * separators between them; this is for one block of free-form content.
 */
export function Card({ children, header, footer, style }: Props) {
  return (
    <View style={[{ backgroundColor: colors.surface, borderRadius: radius.card, padding: space.lg }, style]}>
      {header ? <View style={{ marginBottom: space.md }}>{header}</View> : null}
      {children}
      {footer ? (
        <View
          style={{
            marginTop: space.md,
            paddingTop: space.md,
            borderTopWidth: 1,
            borderTopColor: colors.separator,
          }}
        >
          {footer}
        </View>
      ) : null}
    </View>
  );
}
