import { router } from 'expo-router';
import { View } from 'react-native';
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { Card } from '@/src/ui/Card';
import { Badge } from '@/src/ui/Badge';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { useSignOut } from '@/src/features/auth/useSession';
import { colors, space } from '@/src/ui/tokens';
import { t, roleLabel } from '@/src/i18n/it';

/** "Maria Rossi" -> "MR"; a single name -> its first letter. */
function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

export default function AltroScreen() {
  const { profile } = useSessionContext();
  const signOut = useSignOut();

  async function leave() {
    await signOut();
    router.replace('/(auth)/accedi');
  }

  const fullName = profile?.full_name ?? '';

  return (
    <Screen title={t.nav.altro}>
      <Card style={{ marginBottom: space.xl }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.md }}>
          <View
            style={{
              width: 56,
              height: 56,
              borderRadius: 28,
              backgroundColor: colors.blueTint,
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Text variant="headline" tone="blue">
              {initials(fullName)}
            </Text>
          </View>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text variant="headline" numberOfLines={1}>
              {fullName}
            </Text>
            <Text variant="subhead" tone="secondary" numberOfLines={1} style={{ marginTop: 2 }}>
              {profile?.business.name ?? ''}
            </Text>
          </View>
          {profile ? <Badge label={roleLabel(profile.role)} tone="blue" /> : null}
        </View>
      </Card>

      <ListGroup>
        <ListRow title={t.nav.registro} subtitle={t.nav.comingSoon} />
        <ListRow title={t.nav.fornitori} subtitle={t.nav.comingSoon} />
        {profile?.role === 'titolare' ? <ListRow title={t.nav.utenti} subtitle={t.nav.comingSoon} /> : null}
        <ListRow title={t.nav.impostazioni} subtitle={t.nav.comingSoon} />
      </ListGroup>

      <ListGroup>
        <ListRow title={t.nav.signOut} onPress={leave} tone="destructive" showChevron={false} />
      </ListGroup>
    </Screen>
  );
}
