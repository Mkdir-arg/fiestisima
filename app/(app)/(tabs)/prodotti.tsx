import { useState } from 'react';
import { router } from 'expo-router';
import { Pressable, View } from 'react-native';
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { Icon } from '@/src/ui/Icon';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { SearchField } from '@/src/ui/SearchField';
import { EmptyState } from '@/src/ui/EmptyState';
import { useProducts } from '@/src/features/products/queries';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { colors, radius, space, HIT_SIZE } from '@/src/ui/tokens';
import { t } from '@/src/i18n/it';

export default function ProdottiScreen() {
  const [search, setSearch] = useState('');
  const trimmedSearch = search.trim();
  const { data, isLoading, error } = useProducts(search);
  const { profile } = useSessionContext();
  // Hides the control only; the API (Postgres RLS) is the actual authority
  // and rejects the write regardless of what this check lets through.
  const canEdit = profile?.role === 'titolare' || profile?.role === 'responsabile';

  return (
    <Screen
      title={t.products.title}
      right={
        canEdit ? (
          <Pressable
            role="button"
            accessibilityLabel={t.products.add}
            onPress={() => router.push('/(app)/prodotti/nuovo')}
            style={{ minHeight: HIT_SIZE, minWidth: HIT_SIZE, alignItems: 'center', justifyContent: 'center' }}
          >
            <Icon name="add" size={26} color={colors.blue} />
          </Pressable>
        ) : undefined
      }
    >
      <View style={{ marginBottom: space.lg }}>
        <SearchField
          value={search}
          onChangeText={setSearch}
          label={t.common.search}
          placeholder={t.oggi.searchProducts}
          clearLabel={t.common.clearSearch}
        />
      </View>

      {error ? <Text tone="red">{t.errors.generic}</Text> : null}

      {isLoading ? <ProductListSkeleton /> : null}

      {!isLoading && !error && data && data.length === 0 && !trimmedSearch ? (
        <EmptyState
          icon="products"
          title={t.products.emptyTitle}
          actionLabel={canEdit ? t.products.emptyAction : undefined}
          onAction={canEdit ? () => router.push('/(app)/prodotti/nuovo') : undefined}
        />
      ) : null}

      {!isLoading && !error && data && data.length === 0 && trimmedSearch ? (
        <EmptyState icon="search" title={t.products.noResultsTitle} message={t.products.noResultsMessage(trimmedSearch)} />
      ) : null}

      {!isLoading && data && data.length > 0 ? (
        <ListGroup>
          {data.map((product) => (
            <ListRow
              key={product.id}
              title={product.name}
              subtitle={`${product.storage} · ${product.unit}`}
              onPress={() => router.push(`/(app)/prodotti/${product.id}`)}
            />
          ))}
        </ListGroup>
      ) : null}
    </Screen>
  );
}

/** A quiet placeholder shaped like the rows it is about to become, rather
 * than the word "Caricamento…" sitting alone on the page. */
function ProductListSkeleton() {
  return (
    <View
      accessibilityLabel={t.common.loading}
      style={{ backgroundColor: colors.surface, borderRadius: radius.card, overflow: 'hidden' }}
    >
      {[0, 1, 2, 3].map((row) => (
        <View
          key={row}
          style={{
            minHeight: HIT_SIZE + 10,
            justifyContent: 'center',
            gap: 6,
            paddingHorizontal: space.lg,
            paddingVertical: 11,
            borderTopWidth: row > 0 ? 1 : 0,
            borderTopColor: colors.separator,
          }}
        >
          <View style={{ height: 14, width: '55%', borderRadius: 4, backgroundColor: colors.fill }} />
          <View style={{ height: 10, width: '35%', borderRadius: 4, backgroundColor: colors.fill }} />
        </View>
      ))}
    </View>
  );
}
