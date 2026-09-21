import { useState } from 'react';
import { View, ScrollView } from 'react-native';
import { router } from 'expo-router';
import { Text } from '@/src/ui/Text';
import { Field } from '@/src/ui/Field';
import { Button } from '@/src/ui/Button';
import { ListGroup } from '@/src/ui/ListGroup';
import { colors, space } from '@/src/ui/tokens';
import { signIn } from '@/src/features/auth/api';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { t } from '@/src/i18n/it';

export default function AccediScreen() {
  const { refresh, deactivated } = useSessionContext();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    const result = await signIn(email.trim(), password);
    if (result.ok) {
      // useSession owns the ['me'] cache; force it to re-check now that
      // tokens are stored, instead of waiting for its own polling.
      await refresh();
      router.replace('/(app)/(tabs)/prodotti');
    } else {
      setBusy(false);
      setError(result.message);
    }
  }

  // A deactivated account bounces here from the app shell with no error of
  // its own yet; show that state until the person tries to sign in again.
  const message = error ?? (deactivated ? t.auth.deactivated : null);

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={{ padding: space.lg, paddingTop: 72, maxWidth: 480, width: '100%', alignSelf: 'center' }}
    >
      <Text variant="largeTitle" style={{ marginBottom: space.xl }}>
        {t.auth.signInTitle}
      </Text>

      <ListGroup>
        <Field
          label={t.auth.email}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
          textContentType="emailAddress"
        />
        <Field
          label={t.auth.password}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          textContentType="password"
        />
      </ListGroup>

      {message ? (
        <Text variant="footnote" tone="red" style={{ marginBottom: space.md, marginLeft: space.xs }}>
          {message}
        </Text>
      ) : null}

      <Button title={t.auth.submit} onPress={submit} loading={busy} disabled={!email || !password} />

      <View style={{ height: space.lg }} />
      <Text variant="footnote" tone="blue" style={{ textAlign: 'center' }}>
        {t.auth.forgot}
      </Text>
    </ScrollView>
  );
}
