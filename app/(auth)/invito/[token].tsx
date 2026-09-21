import { useState } from 'react';
import { ScrollView } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Text } from '@/src/ui/Text';
import { Field } from '@/src/ui/Field';
import { Button } from '@/src/ui/Button';
import { ListGroup } from '@/src/ui/ListGroup';
import { colors, space } from '@/src/ui/tokens';
import { acceptInvitation, getInvitationPreview } from '@/src/features/auth/api';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { t } from '@/src/i18n/it';

export default function InvitoScreen() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { refresh } = useSessionContext();

  const previewQuery = useQuery({
    queryKey: ['invitation', token],
    enabled: Boolean(token),
    queryFn: () => getInvitationPreview(token),
  });

  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    const result = await acceptInvitation(token, fullName.trim(), password);
    if (result.ok) {
      await refresh();
      router.replace('/(app)/(tabs)/prodotti');
    } else {
      setBusy(false);
      setError(result.message);
    }
  }

  if (previewQuery.isLoading) {
    return (
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentContainerStyle={{ padding: space.lg, paddingTop: 72 }}
      >
        <Text tone="secondary">{t.common.loading}</Text>
      </ScrollView>
    );
  }

  const outcome = previewQuery.data;

  if (!outcome || !outcome.ok) {
    return (
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentContainerStyle={{ padding: space.lg, paddingTop: 72, maxWidth: 480, width: '100%', alignSelf: 'center' }}
      >
        <Text variant="largeTitle" style={{ marginBottom: space.lg }}>
          {t.invite.title}
        </Text>
        <Text tone="red">{outcome?.message ?? t.invite.expired}</Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={{ padding: space.lg, paddingTop: 72, maxWidth: 480, width: '100%', alignSelf: 'center' }}
    >
      <Text variant="largeTitle" style={{ marginBottom: space.sm }}>
        {t.invite.title}
      </Text>
      <Text tone="secondary" style={{ marginBottom: space.xl }}>
        {outcome.preview.full_name} · {outcome.preview.business_name}
      </Text>
      <ListGroup>
        <Field label={t.invite.fullName} value={fullName} onChangeText={setFullName} />
        <Field
          label={t.invite.choosePassword}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          textContentType="newPassword"
        />
      </ListGroup>
      {error ? (
        <Text variant="footnote" tone="red" style={{ marginBottom: space.md, marginLeft: space.xs }}>
          {error}
        </Text>
      ) : null}
      <Button
        title={t.invite.submit}
        onPress={submit}
        loading={busy}
        disabled={fullName.length < 2 || password.length < 8}
      />
    </ScrollView>
  );
}
