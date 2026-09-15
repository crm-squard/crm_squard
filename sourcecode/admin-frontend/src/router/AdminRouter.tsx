import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";
import { lazy, Suspense, type ReactNode } from "react";
import AdminLayout from "../components/AdminLayout";
import RequireAuth from "../components/RequireAuth";

const DashboardPage = lazy(() => import("../pages/DashboardPage"));
const OrderDetailPage = lazy(() => import("../pages/OrderDetailPage"));
const OrdersPage = lazy(() => import("../pages/OrdersPage"));
const RagPage = lazy(() => import("../pages/RagPage"));
const LoginPage = lazy(() => import("../pages/LoginPage"));
const CompanySelectPage = lazy(() => import("../pages/CompanySelectPage"));
const CompanySettingsPage = lazy(() => import("../pages/CompanySettingsPage"));

function PageLoading() {
  return <div className="route-loading" role="status">頁面載入中…</div>;
}

function loadPage(page: ReactNode) {
  return <Suspense fallback={<PageLoading />}>{page}</Suspense>;
}

const router = createBrowserRouter([
  { path: "login", element: loadPage(<LoginPage />) },
  { path: "select-company", element: loadPage(<CompanySelectPage />) },
  {
    element: (
      <RequireAuth>
        <AdminLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: loadPage(<DashboardPage />) },
      { path: "orders", element: loadPage(<OrdersPage />) },
      { path: "orders/:orderId", element: loadPage(<OrderDetailPage />) },
      { path: "rag", element: loadPage(<RagPage />) },
      { path: "company-settings", element: loadPage(<CompanySettingsPage />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export default function AdminRouter() {
  return <RouterProvider router={router} />;
}
