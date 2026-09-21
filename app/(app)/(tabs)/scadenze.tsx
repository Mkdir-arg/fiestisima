import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { t } from '@/src/i18n/it';

export default function ScadenzeScreen() {
  return (
    <Screen title={t.nav.scadenze}>
      <Text tone="secondary">{t.nav.comingSoon}</Text>
    </Screen>
  );
}
