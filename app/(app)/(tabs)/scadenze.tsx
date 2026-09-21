import { Screen } from '@/src/ui/Screen';
import { EmptyState } from '@/src/ui/EmptyState';
import { t } from '@/src/i18n/it';

export default function ScadenzeScreen() {
  return (
    <Screen title={t.nav.scadenze}>
      <EmptyState icon="expiry" title={t.nav.comingSoonTitle} message={t.nav.comingSoon} />
    </Screen>
  );
}
