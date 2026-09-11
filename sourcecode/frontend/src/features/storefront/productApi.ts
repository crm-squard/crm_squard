import type { Product, ProductListResponse } from "./types";

const PRODUCT_API_BASE_URL = import.meta.env.VITE_ORDER_API_BASE_URL || "http://localhost:8001";

interface ProductApiItem {
  ProductID: string;
  ProductNameZH: string;
  ProductNameEN: string;
  Category: string;
  Description: string;
  DescriptionShort: string;
  ImageUrl?: string;
  OriginalPrice?: string | number | null;
  RealPrice?: string | number | null;
  id: string;
}

interface ProductApiResponse {
  pidx: number;
  pno: number;
  count: number;
  products: ProductApiItem[];
}

export class ProductCatalogError extends Error {}

function toPrice(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const normalizedValue = typeof value === "string" ? value.trim() : value;
  if (normalizedValue === "") return null;
  const price = typeof normalizedValue === "number" ? normalizedValue : Number(normalizedValue);
  return Number.isFinite(price) && price >= 0 ? price : null;
}

function toStorefrontProduct(product: ProductApiItem): Product {
  const productId = Number(product.ProductID);
  if (!Number.isSafeInteger(productId)) {
    throw new ProductCatalogError("商品資料缺少有效的 ProductID。");
  }

  return {
    productID: productId,
    productNameEN: product.ProductNameEN,
    productNameZH: product.ProductNameZH,
    category: product.Category,
    originalPrice: toPrice(product.OriginalPrice),
    realPrice: toPrice(product.RealPrice),
    descriptionShort: product.DescriptionShort || product.Description,
    imageUrl: product.ImageUrl?.trim() ?? "",
  };
}

export async function fetchProductPage(
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<ProductListResponse> {
  const response = await fetch(
    `${PRODUCT_API_BASE_URL}/api/v1/Product?pidx=${page}&pno=${pageSize}`,
    { signal },
  );

  if (!response.ok) {
    throw new ProductCatalogError(`商品列表載入失敗（${response.status}）。請稍後重試。`);
  }

  const payload = await response.json() as ProductApiResponse;
  return {
    pidx: payload.pidx,
    pno: payload.pno,
    count: payload.count,
    products: payload.products.map(toStorefrontProduct),
  };
}
