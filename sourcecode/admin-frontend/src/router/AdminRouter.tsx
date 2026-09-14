import { Navigate, Route, Routes } from "react-router-dom";
import { lazy, Suspense, type ReactNode } from "react";
import AdminLayout from "../components/AdminLayout";

const DashboardPage = lazy(() => import("../pages/DashboardPage"));
const OrderDetailPage = lazy(() => import("../pages/OrderDetailPage"));
const OrdersPage = lazy(() => import("../pages/OrdersPage"));
const RagPage = lazy(() => import("../pages/RagPage"));

function PageLoading() {
  return <div className="route-loading" role="status">頁面載入中…</div>;
}

function loadPage(page: ReactNode) {
  return <Suspense fallback={<PageLoading />}>{page}</Suspense>;
}

export default function AdminRouter() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={loadPage(<DashboardPage />)} />
        <Route path="orders" element={loadPage(<OrdersPage />)} />
        <Route path="orders/:orderId" element={loadPage(<OrderDetailPage />)} />
        <Route path="rag" element={loadPage(<RagPage />)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
