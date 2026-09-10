import type { Product } from "./types";

type ProductSupplement = Pick<Product, "productID" | "unitPrice" | "imagePath">;

export const PRODUCTS: ProductSupplement[] = [
  { productID: 2001, unitPrice: 18, imagePath: "/images/product/large/Wireless%20Mouse.jpg" },
  { productID: 2002, unitPrice: 62, imagePath: "/images/product/large/Mechanical%20Keyboard.jpg" },
  { productID: 2003, unitPrice: 9, imagePath: "/images/product/large/USB-C%20Cable.jpg" },
  { productID: 2004, unitPrice: 35, imagePath: "/images/product/large/Power%20Bank.jpg" },
  { productID: 2005, unitPrice: 28, imagePath: "/images/product/large/Laptop%20Stand.jpg" },
  { productID: 2006, unitPrice: 48, imagePath: "/images/product/large/Webcam.jpg" },
  { productID: 2007, unitPrice: 75, imagePath: "/images/product/large/Headphones.jpg" },
  { productID: 2008, unitPrice: 14, imagePath: "/images/product/large/Phone%20Case.jpg" },
  { productID: 2009, unitPrice: 120, imagePath: "/images/product/large/Smart%20Watch.jpg" },
  { productID: 2010, unitPrice: 55, imagePath: "/images/product/large/Fitness%20Band.jpg" },
  { productID: 2011, unitPrice: 32, imagePath: "/images/product/large/Desk%20Lamp.jpg" },
  { productID: 2012, unitPrice: 180, imagePath: "/images/product/large/Office%20Chair.jpg" },
  { productID: 2013, unitPrice: 7, imagePath: "/images/product/large/Notebook.jpg" },
  { productID: 2014, unitPrice: 42, imagePath: "/images/product/large/Backpack.jpg" },
  { productID: 2015, unitPrice: 58, imagePath: "/images/product/large/Bluetooth%20Speaker.jpg" },
  { productID: 2016, unitPrice: 21, imagePath: "/images/product/large/Monitor.jpg" },
  { productID: 2017, unitPrice: 11, imagePath: "/images/product/large/HDMI%20Cable.jpg" },
  { productID: 2018, unitPrice: 85, imagePath: "/images/product/large/Microphone.jpg" },
  { productID: 2019, unitPrice: 260, imagePath: "/images/product/large/Tablet.jpg" },
  { productID: 2020, unitPrice: 68, imagePath: "/images/product/large/Gaming%20Controller.jpg" },
];
