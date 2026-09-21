import { useEffect, useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { View } from 'react-native';
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { Field } from '@/src/ui/Field';
import { Button } from '@/src/ui/Button';
import { useProduct } from '@/src/features/products/queries';
import { useUpdateProduct } from '@/src/features/products/mutations';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { productSchema, UNITS, STORAGES } from '@/src/features/products/schema';
import { ApiError } from '@/src/lib/api';
import { space } from '@/src/ui/tokens';
import { t } from '@/src/i18n/it';

// See app/(app)/prodotti/nuovo.tsx: same reasoning, shared verbatim rather
// than promoted to a helper module not on the task's file list.
function describeWriteError(err: unknown): string {
  if (err instanceof ApiError && (err.status === 403 || err.status === 404)) {
    return t.errors.notPermitted;
  }
  return err instanceof Error ? err.message : t.errors.generic;
}

export default function ProdottoScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, isLoading, error } = useProduct(id);
  const { profile } = useSessionContext();
  // Hides editing only; the API rejects the write for a role that cannot
  // update products regardless of what this check lets through.
  const canEdit = profile?.role === 'titolare' || profile?.role === 'responsabile';
  const update = useUpdateProduct(id);

  const [name, setName] = useState('');
  const [barcode, setBarcode] = useState('');
  const [unit, setUnit] = useState<(typeof UNITS)[number]>('pz');
  const [storage, setStorage] = useState<(typeof STORAGES)[number]>('dispensa');
  const [minStock, setMinStock] = useState('0');
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!data) return;
    setName(data.name);
    setBarcode(data.barcode ?? '');
    setUnit(data.unit as (typeof UNITS)[number]);
    setStorage(data.storage as (typeof STORAGES)[number]);
    setMinStock(String(data.min_stock));
  }, [data]);

  if (isLoading) {
    return (
      <Screen title={t.common.loading}>
        <Text tone="secondary">{t.common.loading}</Text>
      </Screen>
    );
  }
  if (error || !data) {
    return (
      <Screen title={t.errors.generic}>
        <Text tone="red">{t.errors.generic}</Text>
      </Screen>
    );
  }

  if (!canEdit) {
    return (
      <Screen title={data.name}>
        <ListGroup>
          <ListRow title={t.products.barcode} right={<Text tone="secondary">{data.barcode ?? '—'}</Text>} />
          <ListRow title={t.products.unit} right={<Text tone="secondary">{data.unit}</Text>} />
          <ListRow title={t.products.storage} right={<Text tone="secondary">{data.storage}</Text>} />
          <ListRow
            title={t.products.minStock}
            right={<Text tone="secondary">{String(data.min_stock)}</Text>}
          />
        </ListGroup>
      </Screen>
    );
  }

  async function submit() {
    setFormError(null);
    const parsed = productSchema.safeParse({
      name,
      barcode,
      unit,
      storage,
      min_stock: Number(minStock.replace(',', '.')) || 0,
      has_expiry: data!.has_expiry,
    });
    if (!parsed.success) {
      setFormError(t.errors.generic);
      return;
    }
    try {
      await update.mutateAsync(parsed.data);
    } catch (e) {
      setFormError(describeWriteError(e));
    }
  }

  return (
    <Screen title={data.name}>
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

      {formError ? (
        <Text tone="red" variant="footnote" style={{ marginBottom: space.md }}>
          {formError}
        </Text>
      ) : null}

      <Button title={t.common.save} onPress={submit} loading={update.isPending} disabled={!name.trim()} />
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
