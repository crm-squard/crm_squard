import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { token, selectedCompanyId } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  if (!selectedCompanyId) return <Navigate to="/select-company" replace />;
  return <>{children}</>;
}
