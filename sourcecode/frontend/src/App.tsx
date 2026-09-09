import SmartCRMChatWidget from "./features/chat/SmartCRMChatWidget";
import AdminDocumentsPage from "./features/documents/AdminDocumentsPage";

export default function App() {
  if (window.location.pathname === "/admin") {
    return <AdminDocumentsPage />;
  }
  return <SmartCRMChatWidget />;
}
