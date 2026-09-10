import { PRODUCTS } from "./products";
import type { Product, ProductListResponse } from "./types";

const PRODUCT_API_BASE_URL = import.meta.env.VITE_ORDER_API_BASE_URL || "http://localhost:8001";

interface ProductApiItem {
  ProductID: string;
  ProductNameZH: string;
  ProductNameEN: string;
  Category: string;
  Description: string;
  DescriptionShort: string;
  id: string;
}

interface ProductApiResponse {
  pidx: number;
  pno: number;
  count: number;
  products: ProductApiItem[];
}

export class ProductCatalogError extends Error {}

function toStorefrontProduct(product: ProductApiItem): Product {
  const productId = Number(product.ProductID);
  if (!Number.isSafeInteger(productId)) {
    throw new ProductCatalogError("商品資料缺少有效的 ProductID。");
  }

  // 目前商品清單 API 未提供單價；結帳流程仍使用既有商品編號對照的資料價格。
  const fallbackProduct = PRODUCTS.find((candidate) => candidate.productID === productId);
  return {
    productID: productId,
    productNameEN: product.ProductNameEN,
    productNameZH: product.ProductNameZH,
    category: product.Category,
    unitPrice: fallbackProduct?.unitPrice ?? 0,
    descriptionShort: product.DescriptionShort || product.Description,
    imagePath: fallbackProduct?.imagePath ?? "",
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
