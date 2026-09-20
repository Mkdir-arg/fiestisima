export type LotStatus = 'scaduto' | 'in_scadenza' | 'ok' | 'senza_scadenza';

const MS_PER_DAY = 86_400_000;

/** Días calendario desde `from` hasta `isoDate`. Negativo si ya pasó. */
export function daysUntil(isoDate: string, from: Date): number {
  const [y, m, d] = isoDate.split('-').map(Number) as [number, number, number];
  const target = Date.UTC(y, m - 1, d);
  const start = Date.UTC(from.getUTCFullYear(), from.getUTCMonth(), from.getUTCDate());
  return Math.round((target - start) / MS_PER_DAY);
}

export function lotStatus(
  expiresOn: string | null,
  today: Date,
  thresholdDays: number,
): LotStatus {
  if (expiresOn === null) return 'senza_scadenza';
  const days = daysUntil(expiresOn, today);
  if (days < 0) return 'scaduto';
  if (days <= thresholdDays) return 'in_scadenza';
  return 'ok';
}
