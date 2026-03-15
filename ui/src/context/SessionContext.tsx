import React, { createContext, useContext, useState, ReactNode } from 'react';

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
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);

  return (
    <SessionContext.Provider value={{ selectedConnectionId, setSelectedConnectionId, sessionId, setSessionId, sessionInfo, setSessionInfo }}>
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
