import { Redirect, Stack } from 'expo-router';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

export default function AuthLayout() {
  const { session, profile, isLoading } = useSessionContext();

  // Same "block while loading" rule the app group uses. Without it, an
  // already-signed-in person who opens /accedi directly sees the login
  // form for one round trip, until /auth/me answers and the redirect
  // below fires.
  if (isLoading) {
    return null;
  }

  if (session && profile) {
    return <Redirect href="/(app)/(tabs)/prodotti" />;
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}
