import { router } from 'expo-router';
import { Screen } from '@/src/ui/Screen';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { useSignOut } from '@/src/features/auth/useSession';
import { t } from '@/src/i18n/it';

export default function AltroScreen() {
  const { profile } = useSessionContext();
  const signOut = useSignOut();

  async function leave() {
    await signOut();
    router.replace('/(auth)/accedi');
  }

  return (
    <Screen title={t.nav.altro}>
      <ListGroup>
        <ListRow title={profile?.full_name ?? ''} subtitle={profile?.role ?? ''} />
        <ListRow title={profile?.business.name ?? ''} />
      </ListGroup>
      <ListGroup>
        <ListRow title={t.nav.signOut} onPress={leave} />
      </ListGroup>
    </Screen>
  );
}
