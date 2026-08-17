import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import * as api from "./api";
import type { User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        // Access token lives in memory, so a page reload loses it. Ask the
        // backend for a fresh one using the HttpOnly refresh cookie; 401
        // just means "logged out".
        const refreshed = await api.refreshAccess();
        if (refreshed) {
          setUser(await api.fetchMe());
        }
      } catch {
        api.clearTokens();
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    void initializeAuth();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password);
    api.setTokens(tokens.access);
    try {
      setUser(await api.fetchMe());
    } catch (err) {
      // Token issued but profile fetch failed: don't leave a half-session
      // (token set, user null). Clear and let the page surface the error.
      api.clearTokens();
      throw err;
    }
  }, []);

  const loginWithGoogle = useCallback(async (credential: string) => {
    const tokens = await api.googleLogin(credential);
    api.setTokens(tokens.access);
    try {
      setUser(await api.fetchMe());
    } catch (err) {
      api.clearTokens();
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    // Best-effort server-side blacklist + cookie clear; always clear locally.
    void api.logout().catch((err) => {
      console.error("Logout blacklist failed:", err);
    });
    api.clearTokens();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, loginWithGoogle, logout }),
    [user, loading, login, loginWithGoogle, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
