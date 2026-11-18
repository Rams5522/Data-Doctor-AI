import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const AuthContext = createContext(null);

const SESSION_KEY = 'datadoctor_session_v1';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed?.email) setUser(parsed);
    } catch {
      // ignore
    } finally {
      setBooting(false);
    }
  }, []);

  const login = useCallback((userObj) => {
    const safeUser = {
      name: userObj?.name || userObj?.email || 'User',
      email: userObj?.email,
      picture: userObj?.picture || null
    };
    setUser(safeUser);
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify(safeUser));
    } catch {
      // ignore
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    try {
      localStorage.removeItem(SESSION_KEY);
    } catch {
      // ignore
    }
  }, []);

  const value = useMemo(() => ({ user, login, logout, booting }), [user, login, logout, booting]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
