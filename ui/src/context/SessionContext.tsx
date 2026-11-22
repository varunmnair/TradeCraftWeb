import React, { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import { SESSION_EXPIRED_EVENT } from '../utils/sessionEvents';

interface SessionInfo {
  session_id: string;
  user_id: string;
  broker: string;
  expires_at?: string;
  tenant_id?: number;
}

interface SessionContextType {
  selectedConnectionId: number | null;
  setSelectedConnectionId: (id: number | null) => void;
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  sessionInfo: SessionInfo | null;
  setSessionInfo: (info: SessionInfo | null) => void;
  sessionExpiredMessage: string | null;
  clearSessionExpired: () => void;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [sessionExpiredMessage, setSessionExpiredMessage] = useState<string | null>(null);

  useEffect(() => {
    const handleExpired = (event: Event) => {
      const message = (event as CustomEvent<{ message?: string }>).detail?.message;
      setSessionExpiredMessage(message || 'Trading session expired. Reconnect your broker session before placing orders.');
      setSessionId(null);
      setSessionInfo(null);
      localStorage.removeItem('tradecraftx_session_id');
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, handleExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleExpired);
  }, []);

  const clearSessionExpired = useCallback(() => setSessionExpiredMessage(null), []);

  return (
    <SessionContext.Provider value={{
      selectedConnectionId,
      setSelectedConnectionId,
      sessionId,
      setSessionId,
      sessionInfo,
      setSessionInfo,
      sessionExpiredMessage,
      clearSessionExpired,
    }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
}
