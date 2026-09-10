import { useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent } from "react";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Minus,
  PackageCheck,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Trash2,
  Truck,
  X,
} from "lucide-react";
import { submitCheckout } from "./orderApi";
import { MOCK_CUSTOMERS } from "./mockCustomers";
import { CATEGORIES, PRODUCTS } from "./products";
import type { CheckoutCustomer, Product } from "./types";
import { useCart } from "./useCart";
import "./storefront.css";

const CATEGORY_LABELS: Record<string, string> = {
  全部: "全部商品",
  Electronics: "3C 電子",
  Accessories: "配件",
  Wearables: "穿戴裝置",
  "Home Office": "居家辦公",
  Stationery: "文具",
  Gaming: "電競",
};

const PAYMENT_LABELS = {
  Gateway: "線上金流",
  Wallet: "電子錢包",
  CardToCard: "銀行轉帳",
  Cash: "現金付款",
} as const;
const PAYMENT_METHODS = Object.keys(PAYMENT_LABELS) as CheckoutCustomer["PaymentMethod"][];

function getSpriteStyle(productId: number): CSSProperties {
  const spriteIndex = productId - 2001;
  const column = spriteIndex % 5;
  const row = Math.floor(spriteIndex / 5);
  return {
    "--sprite-x": `${column * 25}%`,
    "--sprite-y": `${row * (100 / 3)}%`,
  } as CSSProperties;
}

function ProductCard({ product, onAdd }: { product: Product; onAdd: (product: Product) => void }) {
  return (
    <article className="store-product-card">
      <div
        className="store-product-image"
        style={getSpriteStyle(product.ProductID)}
        role="img"
        aria-label={`${product.displayName}商品圖片`}
      >
        <span className="store-product-id">#{product.ProductID}</span>
      </div>
      <div className="store-product-body">
        <span className="store-product-category">{CATEGORY_LABELS[product.Category]}</span>
        <h3>{product.displayName}</h3>
        <p className="store-product-en">{product.ProductName}</p>
        <p className="store-product-copy">{product.tagline}</p>
        <div className="store-product-footer">
          <strong>${product.UnitPrice.toLocaleString("en-US")}</strong>
          <button type="button" onClick={() => onAdd(product)}>
            <Plus size={18} aria-hidden="true" />
            加入購物車
          </button>
        </div>
      </div>
    </article>
  );
}

export default function Storefront() {
  const [activeCategory, setActiveCategory] = useState("全部");
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedCustomerId, setSelectedCustomerId] = useState(() => String(MOCK_CUSTOMERS[0].CustomerID));
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<CheckoutCustomer["PaymentMethod"]>("Gateway");
  const statusMessageTimerRef = useRef<number | null>(null);
  const { items, addItem, updateQuantity, clearCart, itemCount, total } = useCart();

  const visibleProducts = useMemo(() => activeCategory === "全部"
    ? PRODUCTS
    : PRODUCTS.filter((product) => product.Category === activeCategory), [activeCategory]);
  const selectedCustomer = useMemo(
    () => MOCK_CUSTOMERS.find((customer) => String(customer.CustomerID) === selectedCustomerId) ?? MOCK_CUSTOMERS[0],
    [selectedCustomerId],
  );

  useEffect(() => {
    if (!isCartOpen) setIsCheckoutOpen(false);
  }, [isCartOpen]);

  useEffect(() => () => {
    if (statusMessageTimerRef.current !== null) window.clearTimeout(statusMessageTimerRef.current);
  }, []);

  useEffect(() => {
    if (!isCartOpen) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isSubmitting) setIsCartOpen(false);
    };
    document.body.classList.add("store-no-scroll");
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.classList.remove("store-no-scroll");
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isCartOpen, isSubmitting]);

  function showStatusMessage(message: string) {
    if (statusMessageTimerRef.current !== null) window.clearTimeout(statusMessageTimerRef.current);
    setStatusMessage(message);
    statusMessageTimerRef.current = window.setTimeout(() => {
      setStatusMessage("");
      statusMessageTimerRef.current = null;
    }, 3000);
  }

  function handleAdd(product: Product) {
    addItem(product);
    showStatusMessage(`已將${product.displayName}加入購物車`);
  }

  function openCheckout() {
    const randomCustomer = MOCK_CUSTOMERS[Math.floor(Math.random() * MOCK_CUSTOMERS.length)];
    const randomPaymentMethod = PAYMENT_METHODS[Math.floor(Math.random() * PAYMENT_METHODS.length)];
    setSelectedCustomerId(String(randomCustomer.CustomerID));
    setSelectedPaymentMethod(randomPaymentMethod);
    setErrorMessage("");
    setIsCheckoutOpen(true);
  }

  async function handleCheckout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!items.length || isSubmitting) return;
    const formData = new FormData(event.currentTarget);
    const customer: CheckoutCustomer = {
      CustomerID: Number(formData.get("CustomerID")),
      Age: Number(formData.get("Age")),
      City: String(formData.get("City") || ""),
      SignupDate: String(formData.get("SignupDate") || ""),
      CustomerSegment: String(formData.get("CustomerSegment")) as CheckoutCustomer["CustomerSegment"],
      PhoneNumber: String(formData.get("PhoneNumber") || ""),
      PaymentMethod: String(formData.get("PaymentMethod")) as CheckoutCustomer["PaymentMethod"],
    };
    setErrorMessage("");
    setIsSubmitting(true);

    try {
      await submitCheckout(customer, items);
      clearCart();
      setIsCheckoutOpen(false);
      setIsCartOpen(false);
      showStatusMessage("訂單已送出");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "訂單送出失敗。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="store-shell">
      <a className="store-skip-link" href="#products">跳至商品列表</a>
      <header className="store-header">
        <a className="store-brand" href="#top" aria-label="CRM Select 首頁">
          <span className="store-brand-mark"><Check size={20} aria-hidden="true" /></span>
          <span>CRM <b>SELECT</b></span>
        </a>
        {/* <nav aria-label="主要導覽">
          <a href="#products">新品選物</a>
        </nav> */}
        <button className="store-cart-button" type="button" onClick={() => setIsCartOpen(true)} aria-label={`開啟購物車，共 ${itemCount} 件商品`}>
          <ShoppingBag size={21} aria-hidden="true" />
          <span>購物車</span>
          <b aria-hidden="true">{itemCount}</b>
        </button>
      </header>

      <main id="top">
        <section className="store-hero" aria-labelledby="store-title">
          <div className="store-hero-copy">
            <p className="store-trust-badge"><CheckCircle2 size={18} aria-hidden="true" /> 商品選購</p>
            <h1 id="store-title">日常用品，<br /><em>一次選齊。</em></h1>
            <p>瀏覽各類商品，加入購物車後即可結帳。</p>
            <div className="store-hero-actions">
              <a className="store-primary-link" href="#products">
                瀏覽商品 <ArrowRight size={20} aria-hidden="true" />
              </a>
              {/* <a className="store-secondary-link" href="#benefits">了解購物保障</a> */}
            </div>
          </div>
          <div className="store-hero-art" aria-hidden="true">
            <span className="store-shape store-shape-one" />
            <span className="store-shape store-shape-two" />
            <div className="store-hero-stat">
              <b>20</b>
              <span>件生活選物</span>
            </div>
            <div className="store-hero-badge">GOOD CHOICE<br />GOOD DAY</div>
          </div>
        </section>

        <section className="store-products-section" id="products" aria-labelledby="products-title">
          <div className="store-section-heading">
            <div>
              <p className="store-kicker">SHOP THE COLLECTION</p>
              <h2 id="products-title">全部商品</h2>
            </div>
            <p>查看商品價格並加入購物車。</p>
          </div>
          <div className="store-filters" aria-label="商品分類">
            {CATEGORIES.map((category) => (
              <button
                key={category}
                type="button"
                className={activeCategory === category ? "is-active" : ""}
                aria-pressed={activeCategory === category}
                onClick={() => setActiveCategory(category)}
              >
                {CATEGORY_LABELS[category]}
              </button>
            ))}
          </div>
          <div className="store-product-grid">
            {visibleProducts.map((product) => (
              <ProductCard key={product.ProductID} product={product} onAdd={handleAdd} />
            ))}
          </div>
        </section>
      </main>

      <footer className="store-footer">
        <span>CRM SELECT</span>
        <p>Good tools. Better days.</p>
      </footer>

      {isCartOpen && (
        <div className="store-cart-layer">
          <button className="store-cart-scrim" type="button" onClick={() => !isSubmitting && setIsCartOpen(false)} aria-label="關閉購物車" />
          <aside className="store-cart-drawer" role="dialog" aria-modal="true" aria-labelledby="cart-title">
            <div className="store-cart-head">
              <div>
                <p>{isCheckoutOpen ? "CHECKOUT" : "YOUR PICKS"}</p>
                <h2 id="cart-title">{isCheckoutOpen ? "填寫訂購資料" : `購物車・${itemCount} 件`}</h2>
              </div>
              <button type="button" onClick={() => setIsCartOpen(false)} disabled={isSubmitting} aria-label="關閉購物車"><X aria-hidden="true" /></button>
            </div>

            {!isCheckoutOpen ? (
              <>
                <div className="store-cart-items">
                  {!items.length && (
                    <div className="store-empty-cart">
                      <ShoppingBag size={40} aria-hidden="true" />
                      <h3>購物車尚無商品</h3>
                      <p>請先瀏覽商品並加入購物車。</p>
                      <button type="button" onClick={() => setIsCartOpen(false)}>繼續購物</button>
                    </div>
                  )}
                  {items.map(({ product, quantity }) => (
                    <article className="store-cart-item" key={product.ProductID}>
                      <div className="store-cart-thumb" style={getSpriteStyle(product.ProductID)} role="img" aria-label={product.displayName} />
                      <div className="store-cart-item-info">
                        <h3>{product.displayName}</h3>
                        <span>${product.UnitPrice.toLocaleString("en-US")}</span>
                        <div className="store-quantity">
                          <button type="button" onClick={() => updateQuantity(product.ProductID, quantity - 1)} aria-label={`減少${product.displayName}數量`}><Minus size={16} /></button>
                          <output aria-label={`${product.displayName}數量`}>{quantity}</output>
                          <button type="button" onClick={() => updateQuantity(product.ProductID, quantity + 1)} aria-label={`增加${product.displayName}數量`}><Plus size={16} /></button>
                        </div>
                      </div>
                      <button className="store-remove" type="button" onClick={() => updateQuantity(product.ProductID, 0)} aria-label={`移除${product.displayName}`}><Trash2 size={18} /></button>
                    </article>
                  ))}
                </div>
                {!!items.length && (
                  <div className="store-cart-summary">
                    <div><span>商品小計</span><strong>${total.toLocaleString("en-US")}</strong></div>
                    <p>運費與實際付款金額請於結帳頁確認。</p>
                    <button type="button" onClick={openCheckout}>前往結帳 <ArrowRight size={19} aria-hidden="true" /></button>
                  </div>
                )}
              </>
            ) : (
              <form className="store-checkout" onSubmit={handleCheckout}>
                <button className="store-back-button" type="button" onClick={() => setIsCheckoutOpen(false)} disabled={isSubmitting}>返回購物車</button>
                {errorMessage && <div className="store-error" role="alert">{errorMessage}</div>}
                <div className="store-form-grid">
                  <label>顧客編號<span>*</span><input name="CustomerID" type="number" value={selectedCustomer.CustomerID} readOnly required inputMode="numeric" /></label>
                  <label>年齡<span>*</span><input name="Age" type="number" value={selectedCustomer.Age} readOnly required inputMode="numeric" /></label>
                  <label className="store-field-wide">城市<span>*</span><input name="City" type="text" value={selectedCustomer.City} readOnly required autoComplete="address-level2" /></label>
                  <label>註冊日期<span>*</span><input name="SignupDate" type="date" value={selectedCustomer.SignupDate} readOnly required /></label>
                  <label>顧客分群<span>*</span><select name="CustomerSegment" defaultValue="New" required><option value="New">New</option><option value="Regular">Regular</option><option value="VIP">VIP</option></select></label>
                  <label className="store-field-wide">聯絡電話<span>*</span><input name="PhoneNumber" type="tel" value={selectedCustomer.PhoneNumber} readOnly required autoComplete="tel" /></label>
                  <label className="store-field-wide">付款方式<span>*</span><select name="PaymentMethod" value={selectedPaymentMethod} onChange={(event) => setSelectedPaymentMethod(event.target.value as CheckoutCustomer["PaymentMethod"])} required>{Object.entries(PAYMENT_LABELS).map(([value, label]) => <option key={value} value={value}>{label}（{value}）</option>)}</select></label>
                </div>
                <div className="store-checkout-total"><span>訂單總額</span><strong>${total.toLocaleString("en-US")}</strong></div>
                <button className="store-submit-order" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "正在送出訂單…" : "送出訂單"}
                </button>
                <p className="store-checkout-note">送出後將建立訂單；若送出失敗，購物車商品會保留。</p>
              </form>
            )}
          </aside>
        </div>
      )}

      <div className="store-live-region" aria-live="polite" aria-atomic="true">
        {statusMessage && <div className="store-toast"><CheckCircle2 size={19} aria-hidden="true" />{statusMessage}</div>}
      </div>
    </div>
  );
}
