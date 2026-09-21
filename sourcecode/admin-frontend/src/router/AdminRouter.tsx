import {
  Navigate,
  RouterProvider,
  createBrowserRouter,
} from "react-router-dom";
import { lazy, Suspense, type ReactNode } from "react";
import AdminLayout from "../components/AdminLayout";
import RequireAuth from "../components/RequireAuth";
import { ui } from "../uiStyles";

const DashboardPage = lazy(() => import("../pages/DashboardPage"));
const OrderDetailPage = lazy(() => import("../pages/OrderDetailPage"));
const OrdersPage = lazy(() => import("../pages/OrdersPage"));
const RagPage = lazy(() => import("../pages/RagPage"));
const LoginPage = lazy(() => import("../pages/LoginPage"));
const ChatbotSelectPage = lazy(() => import("../pages/ChatbotSelectPage"));
const ChatbotSettingsPage = lazy(() => import("../pages/ChatbotSettingsPage"));
const ChatbotsPage = lazy(() => import("../pages/ChatbotsPage"));
const SummaryPage = lazy(() => import("../pages/SummaryPage"));
const AdminAccountsPage = lazy(() => import("../pages/AdminAccountsPage"));

function PageLoading() {
  return (
    <div className={ui.routeLoading} role="status">
      頁面載入中…
    </div>
  );
}

function loadPage(page: ReactNode) {
  return <Suspense fallback={<PageLoading />}>{page}</Suspense>;
}

const router = createBrowserRouter([
  { path: "login", element: loadPage(<LoginPage />) },
  { path: "select-chatbot", element: loadPage(<ChatbotSelectPage />) },
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
      { path: "chatbot-settings", element: loadPage(<ChatbotSettingsPage />) },
      { path: "chatbots", element: loadPage(<ChatbotsPage />) },
      { path: "summary", element: loadPage(<SummaryPage />) },
      { path: "admin-accounts", element: loadPage(<AdminAccountsPage />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export default function AdminRouter() {
  return <RouterProvider router={router} />;
}
