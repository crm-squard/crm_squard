import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { token, selectedChatbotId } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  if (!selectedChatbotId) return <Navigate to="/select-chatbot" replace />;
  return <>{children}</>;
}
