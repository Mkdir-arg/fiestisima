export type LotStatus = 'scaduto' | 'in_scadenza' | 'ok' | 'senza_scadenza';

const MS_PER_DAY = 86_400_000;
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Calendar days from `from` until `isoDate`. Negative if already past. */
export function daysUntil(isoDate: string, from: Date): number {
  const match = ISO_DATE.exec(isoDate);
  if (!match) {
    throw new Error(`Expected an ISO date (YYYY-MM-DD), received: ${isoDate}`);
  }
  const [, year, month, day] = match;
  const target = Date.UTC(Number(year), Number(month) - 1, Number(day));
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
