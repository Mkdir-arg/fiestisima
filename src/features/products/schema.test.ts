import { productSchema } from './schema';

const valid = {
  name: 'Pomodori pelati 400 g',
  barcode: '8001234567890',
  unit: 'pz' as const,
  storage: 'dispensa' as const,
  min_stock: 24,
  has_expiry: true,
};

describe('productSchema', () => {
  it('accepts a complete product', () => {
    expect(productSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects an empty name', () => {
    const result = productSchema.safeParse({ ...valid, name: '   ' });
    expect(result.success).toBe(false);
  });

  it('trims whitespace from the name', () => {
    const result = productSchema.parse({ ...valid, name: '  Farina 00  ' });
    expect(result.name).toBe('Farina 00');
  });

  it('accepts a product with no barcode', () => {
    const result = productSchema.safeParse({ ...valid, barcode: '' });
    expect(result.success).toBe(true);
    if (result.success) expect(result.data.barcode).toBeNull();
  });

  it('rejects a negative minimum stock', () => {
    expect(productSchema.safeParse({ ...valid, min_stock: -1 }).success).toBe(false);
  });

  it('rejects a unit that does not exist', () => {
    expect(productSchema.safeParse({ ...valid, unit: 'cajas' }).success).toBe(false);
  });
});
