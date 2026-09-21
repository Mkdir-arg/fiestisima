import { useState } from 'react';
import { router } from 'expo-router';
import { Pressable } from 'react-native';
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { Field } from '@/src/ui/Field';
import { useProducts } from '@/src/features/products/queries';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { space, HIT_SIZE } from '@/src/ui/tokens';
import { t } from '@/src/i18n/it';

export default function ProdottiScreen() {
  const [search, setSearch] = useState('');
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
            style={{ minHeight: HIT_SIZE, justifyContent: 'center' }}
          >
            <Text variant="body" tone="blue">
              {t.products.add}
            </Text>
          </Pressable>
        ) : undefined
      }
    >
      <ListGroup>
        <Field label={t.common.search} value={search} onChangeText={setSearch} autoCapitalize="none" />
      </ListGroup>

      {error ? <Text tone="red">{t.errors.generic}</Text> : null}
      {isLoading ? <Text tone="secondary">{t.common.loading}</Text> : null}

      {data && data.length === 0 ? (
        <Text tone="secondary" style={{ marginTop: space.md }}>
          {t.products.empty}
        </Text>
      ) : null}

      {data && data.length > 0 ? (
        <ListGroup>
          {data.map((product) => (
            <ListRow
              key={product.id}
              title={product.name}
              subtitle={product.barcode ?? product.storage}
              onPress={() => router.push(`/(app)/prodotti/${product.id}`)}
            />
          ))}
        </ListGroup>
      ) : null}
    </Screen>
  );
}
