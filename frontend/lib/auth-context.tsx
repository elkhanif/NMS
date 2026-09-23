"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Role = "ADMIN" | "NETWORK_ENGINEER" | "IT_SUPPORT" | "VIEWER";

interface Session {
  email: string | null;
  role: Role | null;
}

interface AuthContextValue extends Session {
  loading: boolean;
  isConfigWriter: boolean;
  isOperator: boolean;
  isAdmin: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  email: null,
  role: null,
  loading: true,
  isConfigWriter: false,
  isOperator: false,
  isAdmin: false,
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>({ email: null, role: null });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => r.json())
      .then((data: Session) => setSession(data))
      .finally(() => setLoading(false));
  }, []);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  }

  const role = session.role;
  const value: AuthContextValue = {
    ...session,
    loading,
    isAdmin: role === "ADMIN",
    isConfigWriter: role === "ADMIN" || role === "NETWORK_ENGINEER",
    isOperator: role === "ADMIN" || role === "NETWORK_ENGINEER" || role === "IT_SUPPORT",
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
