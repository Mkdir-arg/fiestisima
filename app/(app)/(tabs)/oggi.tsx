import { router } from 'expo-router';
import { View } from 'react-native';
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { StatTile } from '@/src/ui/StatTile';
import { Button } from '@/src/ui/Button';
import { useProducts } from '@/src/features/products/queries';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { space } from '@/src/ui/tokens';
import { t } from '@/src/i18n/it';

/**
 * The home tab. Today the only live data anywhere in the app is the
 * product catalogue, so this is built honestly: one real number and two
 * placeholders, laid out exactly where the expiry and stock numbers will
 * drop in once the Blocco A endpoints exist — no redesign needed then,
 * just a prop change.
 */
export default function OggiScreen() {
  const { profile } = useSessionContext();
  const { data, isLoading } = useProducts();
  const canEdit = profile?.role === 'titolare' || profile?.role === 'responsabile';

  return (
    <Screen title={t.nav.oggi}>
      <Text variant="body" tone="secondary" style={{ marginTop: -space.md, marginBottom: space.xl }}>
        {t.oggi.greeting(profile?.business.name ?? '')}
      </Text>

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.md, marginBottom: space.xl }}>
        <StatTile value={isLoading ? '…' : String(data?.length ?? 0)} label={t.oggi.productsInCatalog} />
        <StatTile value="—" label={t.oggi.expiringSoon} caption={t.oggi.comingSoonCaption} />
        <StatTile value="—" label={t.oggi.lowStock} caption={t.oggi.comingSoonCaption} />
      </View>

      <Text variant="headline" style={{ marginBottom: space.md }}>
        {t.oggi.quickActions}
      </Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.md }}>
        {canEdit ? (
          <View style={{ flexGrow: 1, flexBasis: 160 }}>
            <Button title={t.products.add} onPress={() => router.push('/(app)/prodotti/nuovo')} />
          </View>
        ) : null}
        <View style={{ flexGrow: 1, flexBasis: 160 }}>
          <Button
            title={t.oggi.searchProducts}
            variant="secondary"
            onPress={() => router.push('/(app)/(tabs)/prodotti')}
          />
        </View>
      </View>
    </Screen>
  );
}
