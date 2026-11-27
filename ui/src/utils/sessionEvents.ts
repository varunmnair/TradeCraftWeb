export const SESSION_EXPIRED_EVENT = 'tradecraftx-session-expired';
export const SESSION_RESTORE_REQUIRED_EVENT = 'tradecraftx-session-restore-required';
export const SESSION_CHANGED_EVENT = 'tradecraftx-session-changed';

export interface SessionChangedDetail {
  session_id: string | null;
  broker_connection_id: number | null;
}

/** Notify session-scoped UI state that the active trading session changed. */
export function dispatchSessionChanged(detail: SessionChangedDetail): void {
  window.dispatchEvent(
    new CustomEvent<SessionChangedDetail>(SESSION_CHANGED_EVENT, { detail }),
  );
}
