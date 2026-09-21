import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, View, type TextInput } from 'react-native';
import { router } from 'expo-router';
import { Text } from '@/src/ui/Text';
import { Field } from '@/src/ui/Field';
import { Button } from '@/src/ui/Button';
import { Banner } from '@/src/ui/Banner';
import { BrandMark } from '@/src/ui/BrandMark';
import { ListGroup } from '@/src/ui/ListGroup';
import { colors, space, HIT_SIZE } from '@/src/ui/tokens';
import { forgotPassword, signIn } from '@/src/features/auth/api';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { t } from '@/src/i18n/it';

type Notice = { tone: 'red' | 'blue'; message: string };

export default function AccediScreen() {
  const { refresh, deactivated } = useSessionContext();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);
  const passwordRef = useRef<TextInput>(null);

  const canSubmit = email.trim().length > 0 && password.length > 0 && !busy;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setNotice(null);
    const result = await signIn(email.trim(), password);
    if (result.ok) {
      // useSession owns the ['me'] cache; force it to re-check now that
      // tokens are stored, instead of waiting for its own polling.
      await refresh();
      router.replace('/(app)/(tabs)/prodotti');
    } else {
      setBusy(false);
      setNotice({ tone: 'red', message: result.message });
    }
  }

  async function requestReset() {
    const address = email.trim();
    if (!address) {
      // Nothing to send to, and the API would answer 202 anyway - say so
      // here rather than pretending an email went out.
      setNotice({ tone: 'red', message: t.auth.forgotNeedsEmail });
      return;
    }
    // Always the same answer, sent or not: whether an address has an
    // account is not something this screen should reveal.
    await forgotPassword(address);
    setNotice({ tone: 'blue', message: t.auth.forgotSent });
  }

  // A deactivated account bounces here from the app shell with no error of
  // its own yet; show that state until the person tries to sign in again.
  const shown: Notice | null =
    notice ?? (deactivated ? { tone: 'red', message: t.auth.deactivated } : null);

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.background }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        style={{ flex: 1 }}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{
          // Centred on a laptop, top-aligned once the keyboard eats the
          // screen on a phone.
          flexGrow: 1,
          justifyContent: 'center',
          padding: space.lg,
          paddingVertical: space.xxl,
        }}
      >
        <View style={{ width: '100%', maxWidth: 400, alignSelf: 'center' }}>
          <View style={{ alignItems: 'center', marginBottom: space.xxl }}>
            <BrandMark />
            <Text variant="largeTitle" style={{ marginTop: space.lg }}>
              {t.auth.signInTitle}
            </Text>
            <Text
              variant="subhead"
              tone="secondary"
              style={{ marginTop: space.xs, textAlign: 'center' }}
            >
              {t.auth.subtitle}
            </Text>
          </View>

          <ListGroup>
            <Field
              label={t.auth.email}
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="emailAddress"
              autoComplete="email"
              returnKeyType="next"
              onSubmitEditing={() => passwordRef.current?.focus()}
              submitBehavior="submit"
            />
            <Field
              ref={passwordRef}
              label={t.auth.password}
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!revealed}
              textContentType="password"
              autoComplete="current-password"
              returnKeyType="go"
              onSubmitEditing={submit}
              right={
                // The first password anyone types here is the 20 random
                // characters the bootstrap script printed. Typing that
                // blind, on a phone, is a needless way to fail a login.
                <Pressable
                  role="button"
                  accessibilityLabel={revealed ? t.auth.hidePassword : t.auth.showPassword}
                  onPress={() => setRevealed((on) => !on)}
                  hitSlop={space.md}
                  style={{ minHeight: HIT_SIZE, justifyContent: 'center', paddingLeft: space.sm }}
                >
                  <Text variant="footnote" tone="blue">
                    {revealed ? t.auth.hidePassword : t.auth.showPassword}
                  </Text>
                </Pressable>
              }
            />
          </ListGroup>

          {shown ? <Banner tone={shown.tone}>{shown.message}</Banner> : null}

          <Button title={t.auth.submit} onPress={submit} loading={busy} disabled={!canSubmit} />

          <Pressable
            role="button"
            accessibilityLabel={t.auth.forgot}
            onPress={requestReset}
            hitSlop={space.md}
            style={{
              minHeight: HIT_SIZE,
              alignItems: 'center',
              justifyContent: 'center',
              marginTop: space.md,
            }}
          >
            <Text variant="footnote" tone="blue">
              {t.auth.forgot}
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
