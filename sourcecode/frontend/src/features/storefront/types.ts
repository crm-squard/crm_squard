export type CustomerSegment = "New" | "Regular" | "VIP";
export type PaymentMethod = "CardToCard" | "Cash" | "Gateway" | "Wallet";

export interface Product {
  ProductID: number;
  ProductName: string;
  displayName: string;
  Category: string;
  UnitPrice: number;
  tagline: string;
}

export interface CartItem {
  product: Product;
  quantity: number;
}

export interface CheckoutCustomer {
  CustomerID: number;
  Age: number;
  City: string;
  SignupDate: string;
  CustomerSegment: CustomerSegment;
  PhoneNumber: string;
  PaymentMethod: PaymentMethod;
}

export interface CheckoutOrder {
  CustomerID: number;
  OrderDate: string;
  ProductID: number;
  Quantity: number;
  Discount: number;
  PaymentMethod: PaymentMethod;
  Status: "Completed";
  Age: number;
  City: string;
  SignupDate: string;
  CustomerSegment: CustomerSegment;
  ProductName: string;
  Category: string;
  UnitPrice: number;
  Sales: number;
  OrderValue: number;
  PhoneNumber: string;
}

export interface CheckoutResponse {
  id: string;
  collection: string;
  data: CheckoutOrder;
}
