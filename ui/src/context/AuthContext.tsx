import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { MeResponse } from '../types';
import { api } from '../api/client';

interface AuthContextType {
  user: MeResponse | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, firstName?: string, lastName?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const userData = await api.me();
      setUser(userData);
      sessionStorage.setItem('user', JSON.stringify(userData));
    } catch {
      setUser(null);
      sessionStorage.removeItem('user');
    }
  };

  const login = async (email: string, password: string) => {
    await api.login({ email, password });
    await refreshUser();
  };

  const register = async (email: string, password: string, firstName?: string, lastName?: string) => {
    await api.register({ email, password, first_name: firstName, last_name: lastName });
  };

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      sessionStorage.removeItem('user');
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
