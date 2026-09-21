import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, View } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { Text } from '@/src/ui/Text';
import { Field } from '@/src/ui/Field';
import { Button } from '@/src/ui/Button';
import { Banner } from '@/src/ui/Banner';
import { BrandMark } from '@/src/ui/BrandMark';
import { ListGroup } from '@/src/ui/ListGroup';
import { colors, space, HIT_SIZE } from '@/src/ui/tokens';
import { resetPassword } from '@/src/features/auth/api';
import { t } from '@/src/i18n/it';

const MIN_LENGTH = 8;

/**
 * Where the password-reset email lands: the API mails
 * `SITE_URL/reset-password/<token>`. It sets the new password and sends
 * the person to sign in with it - it does not sign them in, because the
 * reset endpoint answers with nothing but success.
 */
export default function ResetPasswordScreen() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (password.length < MIN_LENGTH) {
      setError(t.resetPassword.tooShort);
      return;
    }
    if (password !== repeat) {
      setError(t.resetPassword.mismatch);
      return;
    }
    setBusy(true);
    setError(null);
    const result = await resetPassword(token, password);
    setBusy(false);
    if (result.ok) {
      setDone(true);
    } else {
      setError(result.message);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.background }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        style={{ flex: 1 }}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{
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
              {t.resetPassword.title}
            </Text>
            <Text
              variant="subhead"
              tone="secondary"
              style={{ marginTop: space.xs, textAlign: 'center' }}
            >
              {t.resetPassword.subtitle}
            </Text>
          </View>

          {done ? (
            <>
              <Banner tone="blue">{t.resetPassword.done}</Banner>
              <Button
                title={t.resetPassword.backToSignIn}
                onPress={() => router.replace('/(auth)/accedi')}
              />
            </>
          ) : (
            <>
              <ListGroup>
                <Field
                  label={t.resetPassword.newPassword}
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!revealed}
                  textContentType="newPassword"
                  autoComplete="new-password"
                  right={
                    <Pressable
                      role="button"
                      accessibilityLabel={revealed ? t.auth.hidePassword : t.auth.showPassword}
                      onPress={() => setRevealed((on) => !on)}
                      hitSlop={space.md}
                      style={{
                        minHeight: HIT_SIZE,
                        justifyContent: 'center',
                        paddingLeft: space.sm,
                      }}
                    >
                      <Text variant="footnote" tone="blue">
                        {revealed ? t.auth.hidePassword : t.auth.showPassword}
                      </Text>
                    </Pressable>
                  }
                />
                <Field
                  label={t.resetPassword.repeat}
                  value={repeat}
                  onChangeText={setRepeat}
                  secureTextEntry={!revealed}
                  textContentType="newPassword"
                  autoComplete="new-password"
                  returnKeyType="go"
                  onSubmitEditing={submit}
                />
              </ListGroup>

              {error ? <Banner tone="red">{error}</Banner> : null}

              <Button
                title={t.resetPassword.submit}
                onPress={submit}
                loading={busy}
                disabled={!password || !repeat || busy}
              />
            </>
          )}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
