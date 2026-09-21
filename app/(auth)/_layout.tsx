import { Redirect, Stack } from 'expo-router';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

export default function AuthLayout() {
  const { session, profile } = useSessionContext();

  if (session && profile) {
    return <Redirect href="/(app)/(tabs)/prodotti" />;
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}
