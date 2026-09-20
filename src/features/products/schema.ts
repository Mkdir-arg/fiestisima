import { z } from 'zod';

export const UNITS = ['pz', 'kg', 'l', 'g', 'ml'] as const;
export const STORAGES = ['frigo', 'freezer', 'dispensa'] as const;

export const productSchema = z.object({
  name: z.string().trim().min(1),
  // A product with no code stores null, not an empty string: that way the
  // per-business unique index does not treat two code-less products as equal.
  barcode: z
    .string()
    .trim()
    .transform((value) => (value === '' ? null : value))
    .nullable(),
  brand: z.string().trim().nullable().optional(),
  unit: z.enum(UNITS),
  storage: z.enum(STORAGES),
  min_stock: z.number().min(0),
  has_expiry: z.boolean(),
});

export type ProductInput = z.infer<typeof productSchema>;
