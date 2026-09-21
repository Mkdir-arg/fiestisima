import { createContext, useContext, type ReactNode } from 'react';
import { useSession } from './useSession';

type SessionContextValue = ReturnType<typeof useSession>;

const SessionContext = createContext<SessionContextValue | null>(null);

/**
 * Mounts `useSession()` exactly once and shares its return value via
 * context. The hook owns token loading and `['me']` cache eviction; a
 * second instance mounted elsewhere would race it (duplicate token reads,
 * duplicate cache evictions on sign-out/deactivation). Every screen and
 * layout must read the session through `useSessionContext` below, never by
 * calling `useSession` directly.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const value = useSession();
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSessionContext(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error('useSessionContext must be used within a SessionProvider');
  }
  return value;
}
