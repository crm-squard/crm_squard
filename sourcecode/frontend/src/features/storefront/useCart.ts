import { useCallback, useEffect, useMemo, useState } from "react";
import { PRODUCTS } from "./products";
import type { CartItem, Product } from "./types";

const STORAGE_KEY = "crm-squad-store-cart";

interface StoredCartItem {
  productId: number;
  quantity: number;
}

function loadCart(): CartItem[] {
  try {
    const rawValue = localStorage.getItem(STORAGE_KEY);
    if (!rawValue) return [];
    const storedItems = JSON.parse(rawValue) as StoredCartItem[];
    if (!Array.isArray(storedItems)) return [];
    return storedItems.flatMap((storedItem) => {
      const product = PRODUCTS.find((candidate) => candidate.ProductID === storedItem.productId);
      if (!product || !Number.isInteger(storedItem.quantity) || storedItem.quantity < 1) return [];
      return [{ product, quantity: Math.min(storedItem.quantity, 99) }];
    });
  } catch {
    return [];
  }
}

export function useCart() {
  const [items, setItems] = useState<CartItem[]>(loadCart);

  useEffect(() => {
    const storedItems: StoredCartItem[] = items.map(({ product, quantity }) => ({
      productId: product.ProductID,
      quantity,
    }));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(storedItems));
  }, [items]);

  const addItem = useCallback((product: Product) => {
    setItems((currentItems) => {
      const existingItem = currentItems.find((item) => item.product.ProductID === product.ProductID);
      if (!existingItem) return [...currentItems, { product, quantity: 1 }];
      return currentItems.map((item) => item.product.ProductID === product.ProductID
        ? { ...item, quantity: Math.min(item.quantity + 1, 99) }
        : item);
    });
  }, []);

  const updateQuantity = useCallback((productId: number, quantity: number) => {
    setItems((currentItems) => quantity < 1
      ? currentItems.filter((item) => item.product.ProductID !== productId)
      : currentItems.map((item) => item.product.ProductID === productId
        ? { ...item, quantity: Math.min(quantity, 99) }
        : item));
  }, []);

  const clearCart = useCallback(() => setItems([]), []);
  const itemCount = useMemo(() => items.reduce((total, item) => total + item.quantity, 0), [items]);
  const total = useMemo(() => items.reduce(
    (sum, item) => sum + item.product.UnitPrice * item.quantity,
    0,
  ), [items]);

  return { items, addItem, updateQuantity, clearCart, itemCount, total };
}
