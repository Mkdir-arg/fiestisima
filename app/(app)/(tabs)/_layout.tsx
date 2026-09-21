import { Link, Tabs, usePathname } from 'expo-router';
import { Pressable, View } from 'react-native';
import { BrandMark } from '@/src/ui/BrandMark';
import { Icon, type IconName } from '@/src/ui/Icon';
import { Text } from '@/src/ui/Text';
import { colors, radius, space, HIT_SIZE } from '@/src/ui/tokens';
import { useLayout } from '@/src/ui/useLayout';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { t, roleLabel } from '@/src/i18n/it';

const TAB_ITEMS = [
  { key: 'oggi', href: '/(app)/(tabs)/oggi', label: t.nav.oggi, icon: 'today' satisfies IconName },
  { key: 'prodotti', href: '/(app)/(tabs)/prodotti', label: t.nav.prodotti, icon: 'products' satisfies IconName },
  { key: 'scadenze', href: '/(app)/(tabs)/scadenze', label: t.nav.scadenze, icon: 'expiry' satisfies IconName },
  { key: 'altro', href: '/(app)/(tabs)/altro', label: t.nav.altro, icon: 'more' satisfies IconName },
] as const;

// The sidebar does not repeat "Altro" as a nav item: the profile row at its
// own bottom takes you there instead (see `Sidebar` below). The route still
// exists and is still registered below, for the narrow tab bar and for
// direct navigation.
const SIDEBAR_ITEMS = TAB_ITEMS.filter((item) => item.key !== 'altro');

/**
 * Below the wide breakpoint the tab bar is the usual bottom bar. At or
 * above it, the same routes are shown as a left sidebar and the bottom tab
 * bar is hidden (its screens still render the matched route, they just
 * lose their own chrome) — a two-column layout without duplicating any
 * routing.
 */
export default function TabsLayout() {
  const { isWide } = useLayout();

  if (isWide) {
    return (
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: colors.background }}>
        <Sidebar />
        <View style={{ flex: 1 }}>
          <Tabs screenOptions={{ headerShown: false, tabBarStyle: { display: 'none' } }}>
            {TAB_ITEMS.map((item) => (
              <Tabs.Screen key={item.key} name={item.key} options={{ title: item.label }} />
            ))}
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
      {TAB_ITEMS.map((item) => (
        <Tabs.Screen
          key={item.key}
          name={item.key}
          options={{
            title: item.label,
            tabBarIcon: ({ color, size }) => <Icon name={item.icon} size={size} color={color} />,
          }}
        />
      ))}
    </Tabs>
  );
}

function Sidebar() {
  const pathname = usePathname();
  const { profile } = useSessionContext();

  return (
    <View
      style={{
        width: 260,
        backgroundColor: colors.surface,
        borderRightWidth: 1,
        borderRightColor: colors.separator,
      }}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: space.md,
          paddingHorizontal: space.lg,
          paddingTop: space.xl,
          paddingBottom: space.lg,
        }}
      >
        <BrandMark size={36} />
        <Text variant="headline" numberOfLines={1} style={{ flex: 1 }}>
          {profile?.business.name ?? 'Fiestisima'}
        </Text>
      </View>

      <View style={{ flex: 1, paddingHorizontal: space.sm }}>
        {SIDEBAR_ITEMS.map((item) => {
          const active = pathname.includes(`/${item.key}`);
          return (
            <Link key={item.key} href={item.href} asChild>
              <Pressable
                role="button"
                accessibilityLabel={item.label}
                accessibilityState={{ selected: active }}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: space.md,
                  minHeight: HIT_SIZE,
                  paddingHorizontal: space.md,
                  borderRadius: radius.control,
                  backgroundColor: active ? colors.blueTint : 'transparent',
                  marginBottom: space.xs,
                }}
              >
                <Icon name={item.icon} size={20} color={active ? colors.blue : colors.textSecondary} />
                <Text variant="body" tone={active ? 'blue' : 'primary'}>
                  {item.label}
                </Text>
              </Pressable>
            </Link>
          );
        })}
      </View>

      <Link href="/(app)/(tabs)/altro" asChild>
        <Pressable
          role="button"
          accessibilityLabel={t.nav.altro}
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: space.md,
            minHeight: HIT_SIZE + 8,
            paddingHorizontal: space.lg,
            paddingVertical: space.md,
            borderTopWidth: 1,
            borderTopColor: colors.separator,
          }}
        >
          <Icon name="person" size={30} color={colors.textSecondary} />
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text variant="body" numberOfLines={1} style={{ fontWeight: '500' }}>
              {profile?.full_name ?? ''}
            </Text>
            <Text variant="footnote" tone="secondary" numberOfLines={1}>
              {profile ? roleLabel(profile.role) : ''}
            </Text>
          </View>
        </Pressable>
      </Link>
    </View>
  );
}
