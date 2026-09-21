import { useState } from 'react';
import { router } from 'expo-router';
import { View } from 'react-native';
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { Field } from '@/src/ui/Field';
import { Button } from '@/src/ui/Button';
import { useCreateProduct } from '@/src/features/products/mutations';
import { productSchema, UNITS, STORAGES } from '@/src/features/products/schema';
import { ApiError } from '@/src/lib/api';
import { space } from '@/src/ui/tokens';
import { t } from '@/src/i18n/it';

/**
 * The list screen hides "Nuovo prodotto" for a role that cannot create
 * products, but the API is the real authority: someone who reaches this
 * screen anyway (a direct URL, a stale tab) gets a 403 or 404 from the
 * write (ruling v2-15 — RLS-filtered writes can come back either way). That
 * is shown as one generic "not permitted" message, never the raw code.
 */
function describeWriteError(err: unknown): string {
  if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
    return t.errors.notPermitted;
  }
  return err instanceof Error ? err.message : t.errors.generic;
}

export default function NuovoProdottoScreen() {
  const create = useCreateProduct();

  const [name, setName] = useState('');
  const [barcode, setBarcode] = useState('');
  const [unit, setUnit] = useState<(typeof UNITS)[number]>('pz');
  const [storage, setStorage] = useState<(typeof STORAGES)[number]>('dispensa');
  const [minStock, setMinStock] = useState('0');
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    const parsed = productSchema.safeParse({
      name,
      barcode,
      unit,
      storage,
      min_stock: Number(minStock.replace(',', '.')) || 0,
      has_expiry: true,
    });
    if (!parsed.success) {
      setError(t.errors.generic);
      return;
    }
    try {
      await create.mutateAsync(parsed.data);
      router.back();
    } catch (e) {
      setError(describeWriteError(e));
    }
  }

  return (
    <Screen title={t.products.add}>
      <ListGroup>
        <Field label={t.products.name} value={name} onChangeText={setName} />
        <Field
          label={t.products.barcode}
          value={barcode}
          onChangeText={setBarcode}
          keyboardType="number-pad"
        />
        <Field
          label={t.products.minStock}
          value={minStock}
          onChangeText={setMinStock}
          keyboardType="decimal-pad"
        />
      </ListGroup>

      <ListGroup header={t.products.unit}>
        {UNITS.map((value) => (
          <Chooser key={value} label={value} selected={unit === value} onPress={() => setUnit(value)} />
        ))}
      </ListGroup>

      <ListGroup header={t.products.storage}>
        {STORAGES.map((value) => (
          <Chooser key={value} label={value} selected={storage === value} onPress={() => setStorage(value)} />
        ))}
      </ListGroup>

      {error ? (
        <Text tone="red" variant="footnote" style={{ marginBottom: space.md }}>
          {error}
        </Text>
      ) : null}

      <Button title={t.common.save} onPress={submit} loading={create.isPending} disabled={!name.trim()} />
      <View style={{ height: space.xxl }} />
    </Screen>
  );
}

function Chooser({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <ListRow
      title={label}
      onPress={onPress}
      right={
        selected ? (
          <Text tone="blue" variant="headline">
            ✓
          </Text>
        ) : undefined
      }
    />
  );
}
