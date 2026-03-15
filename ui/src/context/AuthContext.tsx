import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { MeResponse, AuthUser } from '../types';
import { api } from '../api/client';

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (tenantName: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const userData = await api.me();
      setUser(userData);
      localStorage.setItem('user', JSON.stringify(userData));
    } catch {
      setUser(null);
      localStorage.removeItem('user');
    }
  };

  const login = async (email: string, password: string) => {
    await api.login({ email, password });
    await refreshUser();
  };

  const register = async (tenantName: string, email: string, password: string) => {
    await api.register({ tenant_name: tenantName, email, password });
  };

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      localStorage.removeItem('user');
    }
  };

  useEffect(() => {
    const initAuth = async () => {
      const token = api.getToken();
      if (token) {
        await refreshUser();
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
