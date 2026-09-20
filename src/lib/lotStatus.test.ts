import { lotStatus, daysUntil } from './lotStatus';

const today = new Date('2026-09-20T10:00:00Z');

describe('lotStatus', () => {
  it('marca senza_scadenza cuando el lote no tiene fecha', () => {
    expect(lotStatus(null, today, 7)).toBe('senza_scadenza');
  });

  it('marca scaduto cuando la fecha ya pasó', () => {
    expect(lotStatus('2026-09-19', today, 7)).toBe('scaduto');
  });

  it('marca scaduto el día anterior, no el mismo día', () => {
    expect(lotStatus('2026-09-20', today, 7)).toBe('in_scadenza');
  });

  it('incluye el umbral exacto en in_scadenza', () => {
    expect(lotStatus('2026-09-27', today, 7)).toBe('in_scadenza');
  });

  it('deja fuera el día siguiente al umbral', () => {
    expect(lotStatus('2026-09-28', today, 7)).toBe('ok');
  });

  it('respeta un umbral distinto de 7', () => {
    expect(lotStatus('2026-10-01', today, 14)).toBe('in_scadenza');
    expect(lotStatus('2026-10-01', today, 3)).toBe('ok');
  });
});

describe('daysUntil', () => {
  it('devuelve negativo para una fecha pasada', () => {
    expect(daysUntil('2026-09-17', today)).toBe(-3);
  });

  it('devuelve cero el mismo día', () => {
    expect(daysUntil('2026-09-20', today)).toBe(0);
  });

  it('lanza un error si la fecha viene mal formada', () => {
    expect(() => daysUntil('12/03/2027', today)).toThrow();
  });

  it('lanza un error si a la fecha le faltan segmentos', () => {
    expect(() => daysUntil('2027-03', today)).toThrow();
  });
});
