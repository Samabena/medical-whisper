import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { clearTokens, isAuthenticated, login as apiLogin } from "../api/client";

interface AuthState {
  authenticated: boolean;
  login: (password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState<boolean>(isAuthenticated());

  const value = useMemo<AuthState>(
    () => ({
      authenticated,
      login: async (password: string) => {
        await apiLogin(password);
        setAuthenticated(true);
      },
      logout: () => {
        clearTokens();
        setAuthenticated(false);
      },
    }),
    [authenticated]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans AuthProvider");
  return ctx;
}
