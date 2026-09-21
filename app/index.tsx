import { Redirect } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';
import { useSessionContext } from '@/src/features/auth/SessionProvider';
import { colors } from '@/src/ui/tokens';

export default function Index() {
  const { session, profile, isLoading } = useSessionContext();

  if (isLoading) {
    return (
      <View
        style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}
      >
        <ActivityIndicator color={colors.blue} />
      </View>
    );
  }

  if (session && profile) {
    return <Redirect href="/(app)/(tabs)/prodotti" />;
  }
  return <Redirect href="/(auth)/accedi" />;
}
