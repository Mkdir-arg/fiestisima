import { Link, Tabs, usePathname } from 'expo-router';
import { Pressable, View } from 'react-native';
import { Text } from '@/src/ui/Text';
import { colors, space } from '@/src/ui/tokens';
import { useLayout } from '@/src/ui/useLayout';
import { t } from '@/src/i18n/it';

const NAV_ITEMS = [
  { key: 'prodotti', href: '/(app)/(tabs)/prodotti', label: t.nav.prodotti },
  { key: 'scadenze', href: '/(app)/(tabs)/scadenze', label: t.nav.scadenze },
  { key: 'altro', href: '/(app)/(tabs)/altro', label: t.nav.altro },
] as const;

/**
 * Below the wide breakpoint the tab bar is the usual bottom bar. At or above
 * it, the same three routes are shown as a left sidebar and the bottom tab
 * bar is hidden (its screens still render the matched route, they just lose
 * their own chrome) — a two-column layout without duplicating any routing.
 */
export default function TabsLayout() {
  const { isWide } = useLayout();

  if (isWide) {
    return (
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: colors.background }}>
        <Sidebar />
        <View style={{ flex: 1 }}>
          <Tabs screenOptions={{ headerShown: false, tabBarStyle: { display: 'none' } }}>
            <Tabs.Screen name="prodotti" options={{ title: t.nav.prodotti }} />
            <Tabs.Screen name="scadenze" options={{ title: t.nav.scadenze }} />
            <Tabs.Screen name="altro" options={{ title: t.nav.altro }} />
          </Tabs>
        </View>
      </View>
    );
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.blue,
        tabBarInactiveTintColor: colors.textTertiary,
        tabBarStyle: { backgroundColor: colors.tabBar, borderTopColor: colors.tabBarBorder },
        tabBarLabelStyle: { fontSize: 10, fontWeight: '500' },
      }}
    >
      <Tabs.Screen name="prodotti" options={{ title: t.nav.prodotti }} />
      <Tabs.Screen name="scadenze" options={{ title: t.nav.scadenze }} />
      <Tabs.Screen name="altro" options={{ title: t.nav.altro }} />
    </Tabs>
  );
}

function Sidebar() {
  const pathname = usePathname();

  return (
    <View
      style={{
        width: 240,
        backgroundColor: colors.surface,
        borderRightWidth: 1,
        borderRightColor: colors.separator,
        paddingTop: space.xl,
      }}
    >
      {NAV_ITEMS.map((item) => {
        const active = pathname.includes(`/${item.key}`);
        return (
          <Link key={item.key} href={item.href} asChild>
            <Pressable
              role="button"
              accessibilityLabel={item.label}
              style={{
                paddingHorizontal: space.lg,
                paddingVertical: space.md,
                backgroundColor: active ? colors.blueTint : 'transparent',
              }}
            >
              <Text variant="body" tone={active ? 'blue' : 'primary'}>
                {item.label}
              </Text>
            </Pressable>
          </Link>
        );
      })}
    </View>
  );
}
