import { useQuery } from '@tanstack/react-query';
import { api } from '@/src/lib/api';
import type { components } from '@/src/types/api';

type ProductOut = components['schemas']['ProductOut'];

/**
 * `ProductOut.min_stock` travels over the wire as a string: pydantic
 * serialises a Postgres `numeric` (Python `Decimal`) as a JSON string, not a
 * number, to avoid float rounding. Parsed once here, at the network
 * boundary, so nothing downstream has to remember the quirk.
 */
export type Product = Omit<ProductOut, 'min_stock'> & { min_stock: number };

export function parseProduct(raw: ProductOut): Product {
  return { ...raw, min_stock: Number(raw.min_stock) };
}

export function useProducts(search = '', includeInactive = false) {
  return useQuery({
    queryKey: ['products', search, includeInactive],
    queryFn: async (): Promise<Product[]> => {
      const params = new URLSearchParams();
      if (search.trim()) params.set('search', search.trim());
      if (includeInactive) params.set('include_inactive', 'true');
      const qs = params.toString();
      const raw = await api.get<ProductOut[]>(`/products${qs ? `?${qs}` : ''}`);
      return raw.map(parseProduct);
    },
  });
}

export function useProduct(id: string) {
  return useQuery({
    queryKey: ['product', id],
    enabled: Boolean(id),
    queryFn: async (): Promise<Product> => {
      const raw = await api.get<ProductOut>(`/products/${id}`);
      return parseProduct(raw);
    },
  });
}
