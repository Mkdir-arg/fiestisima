import type { ReactNode } from 'react';
import { ScrollView, View } from 'react-native';
import { Text } from './Text';
import { colors, space } from './tokens';

type Props = { title: string; right?: ReactNode; children: ReactNode };

export function Screen({ title, right, children }: Props) {
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={{
        padding: space.lg,
        paddingTop: space.xl,
        maxWidth: 1100,
        width: '100%',
        alignSelf: 'center',
      }}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          marginBottom: space.lg,
        }}
      >
        <Text variant="largeTitle">{title}</Text>
        {right}
      </View>
      {children}
    </ScrollView>
  );
}
