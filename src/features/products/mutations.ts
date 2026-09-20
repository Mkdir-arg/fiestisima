import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, detailCode } from '@/src/lib/api';
import { t } from '@/src/i18n/it';
import type { components } from '@/src/types/api';
import type { ProductInput } from './schema';
import { parseProduct, type Product } from './queries';

type ProductOut = components['schemas']['ProductOut'];

/**
 * Exception to "detail is always a string": POST/PATCH /products answer 409
 * with `detail` as the OBJECT `{code: 'barcode_taken', name}` (the existing
 * product's name) when the barcode is already used in the business, and with
 * the STRING `detail: 'barcode_locked'` (PATCH only) when the barcode can't
 * change because the product already has lots. Both are translated to
 * Italian here so callers just get a thrown `Error` with copy ready to show.
 */
function rethrowProductError(err: unknown): never {
  if (err instanceof ApiError && err.status === 409) {
    const code = detailCode(err);
    if (code === 'barcode_taken') {
      const name = typeof err.detail === 'object' && err.detail !== null && 'name' in err.detail
        ? String((err.detail as { name: unknown }).name)
        : '';
      throw new Error(t.products.duplicateBarcode(name));
    }
    if (code === 'barcode_locked') {
      throw new Error(t.products.barcodeLocked);
    }
  }
  throw err instanceof Error ? err : new Error(t.errors.generic);
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: ProductInput): Promise<Product> => {
      try {
        const raw = await api.post<ProductOut>('/products', input);
        return parseProduct(raw);
      } catch (err) {
        rethrowProductError(err);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
}

export function useUpdateProduct(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: Partial<ProductInput>): Promise<Product> => {
      try {
        const raw = await api.patch<ProductOut>(`/products/${id}`, input);
        return parseProduct(raw);
      } catch (err) {
        rethrowProductError(err);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product', id] });
    },
  });
}
