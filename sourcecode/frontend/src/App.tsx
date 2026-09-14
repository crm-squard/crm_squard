import SmartCRMChatWidget from "./features/chat/SmartCRMChatWidget";
import AdminDocumentsPage from "./features/documents/AdminDocumentsPage";
import Storefront from "./features/storefront/Storefront";

export default function App() {
  if (window.location.pathname === "/admin") {
    return <AdminDocumentsPage />;
  }
  return (
    <>
      <Storefront />
      <SmartCRMChatWidget />
    </>
  );
}