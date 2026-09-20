import { Children, Fragment, type ReactNode } from 'react';
import { View } from 'react-native';
import { Text } from './Text';
import { colors, radius, space } from './tokens';

type Props = { header?: string; footer?: string; children: ReactNode };

export function ListGroup({ header, footer, children }: Props) {
  const rows = Children.toArray(children);
  return (
    <View style={{ marginBottom: space.xl }}>
      {header ? (
        <Text variant="headline" style={{ marginBottom: space.sm, marginLeft: space.xs }}>
          {header}
        </Text>
      ) : null}
      <View
        style={{
          backgroundColor: colors.surface,
          borderRadius: radius.card,
          overflow: 'hidden',
        }}
      >
        {rows.map((row, i) => (
          <Fragment key={i}>
            {i > 0 ? (
              <View
                style={{ height: 1, backgroundColor: colors.separator, marginLeft: space.lg }}
              />
            ) : null}
            {row}
          </Fragment>
        ))}
      </View>
      {footer ? (
        <Text
          variant="footnote"
          tone="secondary"
          style={{ marginTop: space.sm, marginHorizontal: space.xs }}
        >
          {footer}
        </Text>
      ) : null}
    </View>
  );
}
