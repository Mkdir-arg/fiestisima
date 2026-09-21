import { Redirect, Stack } from 'expo-router';
import { useSessionContext } from '@/src/features/auth/SessionProvider';

export default function AppLayout() {
  const { session, isLoading } = useSessionContext();

  if (isLoading) {
    // useSession is still reading tokens / checking /auth/me: render
    // nothing rather than flashing the sign-in screen for a signed-in user.
    return null;
  }
  if (!session) {
    return <Redirect href="/(auth)/accedi" />;
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}
