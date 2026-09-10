import type { Product } from "./types";

export const PRODUCTS: Product[] = [
  { ProductID: 2001, ProductName: "Wireless Mouse", displayName: "無線滑鼠", Category: "Electronics", UnitPrice: 18, tagline: "低延遲連線與舒適握感，讓工作俐落無束縛。" },
  { ProductID: 2002, ProductName: "Mechanical Keyboard", displayName: "機械式鍵盤", Category: "Electronics", UnitPrice: 62, tagline: "清脆回饋與耐用結構，為每次敲擊增添節奏。" },
  { ProductID: 2003, ProductName: "USB-C Cable", displayName: "USB-C 傳輸線", Category: "Accessories", UnitPrice: 9, tagline: "快充、傳輸與影像輸出，一條完成多種任務。" },
  { ProductID: 2004, ProductName: "Power Bank", displayName: "行動電源", Category: "Electronics", UnitPrice: 35, tagline: "大容量快速供電，行動生活不中斷。" },
  { ProductID: 2005, ProductName: "Laptop Stand", displayName: "筆電支架", Category: "Accessories", UnitPrice: 28, tagline: "抬升視角並加速散熱，打造舒適工作姿勢。" },
  { ProductID: 2006, ProductName: "Webcam", displayName: "網路攝影機", Category: "Electronics", UnitPrice: 48, tagline: "清晰畫質與智慧校正，線上登場更有自信。" },
  { ProductID: 2007, ProductName: "Headphones", displayName: "耳罩式耳機", Category: "Electronics", UnitPrice: 75, tagline: "主動降噪與寬廣音場，保留自己的專注空間。" },
  { ProductID: 2008, ProductName: "Phone Case", displayName: "手機保護殼", Category: "Accessories", UnitPrice: 14, tagline: "輕薄手感搭配軍規防護，俐落守護日常。" },
  { ProductID: 2009, ProductName: "Smart Watch", displayName: "智慧手錶", Category: "Wearables", UnitPrice: 120, tagline: "全天健康追蹤與智慧通知，掌握每個重要時刻。" },
  { ProductID: 2010, ProductName: "Fitness Band", displayName: "智慧手環", Category: "Wearables", UnitPrice: 55, tagline: "輕巧記錄運動與睡眠，讓改變看得見。" },
  { ProductID: 2011, ProductName: "Desk Lamp", displayName: "智慧檯燈", Category: "Home Office", UnitPrice: 32, tagline: "細緻調光與護眼設計，陪伴長時間閱讀。" },
  { ProductID: 2012, ProductName: "Office Chair", displayName: "人體工學辦公椅", Category: "Home Office", UnitPrice: 180, tagline: "完整支撐與透氣坐感，久坐依然自在。" },
  { ProductID: 2013, ProductName: "Notebook", displayName: "筆記本", Category: "Stationery", UnitPrice: 7, tagline: "流暢紙張與靈活收納，接住每一個靈感。" },
  { ProductID: 2014, ProductName: "Backpack", displayName: "後背包", Category: "Accessories", UnitPrice: 42, tagline: "防潑水多隔層設計，通勤裝備井然有序。" },
  { ProductID: 2015, ProductName: "Bluetooth Speaker", displayName: "藍牙喇叭", Category: "Electronics", UnitPrice: 58, tagline: "防水機身與環繞音效，隨處展開好聲音。" },
  { ProductID: 2016, ProductName: "Monitor", displayName: "電腦螢幕", Category: "Electronics", UnitPrice: 21, tagline: "細膩色彩與窄邊框，延伸更寬廣的視野。" },
  { ProductID: 2017, ProductName: "HDMI Cable", displayName: "HDMI 傳輸線", Category: "Accessories", UnitPrice: 11, tagline: "高頻寬穩定傳輸，完整呈現每一幀畫面。" },
  { ProductID: 2018, ProductName: "Microphone", displayName: "麥克風", Category: "Electronics", UnitPrice: 85, tagline: "專業級收音與即時監聽，清楚傳達每句話。" },
  { ProductID: 2019, ProductName: "Tablet", displayName: "平板電腦", Category: "Electronics", UnitPrice: 260, tagline: "輕薄效能兼備，創作娛樂都能流暢切換。" },
  { ProductID: 2020, ProductName: "Gaming Controller", displayName: "電競手把", Category: "Gaming", UnitPrice: 68, tagline: "精準搖桿與低延遲連線，掌控每場對決。" },
];

export const CATEGORIES = ["全部", ...new Set(PRODUCTS.map((product) => product.Category))];
