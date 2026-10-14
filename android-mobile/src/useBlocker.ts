import Androidlib from 'androidlib';
import { useCallback, useEffect, useState } from 'react';
import { AppState } from 'react-native';

// Thin React wrapper over androidlib. State lives natively; this just re-reads
// it after each change and whenever the app comes back to the foreground
// (e.g. returning from the Accessibility settings screen).
export function useBlocker() {
  const [blocked, setBlocked] = useState<string[]>(() => Androidlib.getBlockedDomains());
  const [serviceEnabled, setServiceEnabled] = useState(() => Androidlib.isServiceEnabled());

  const refresh = useCallback(() => {
    setBlocked(Androidlib.getBlockedDomains());
    setServiceEnabled(Androidlib.isServiceEnabled());
  }, []);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });
    return () => sub.remove();
  }, [refresh]);

  const block = useCallback(
    (domains: string[]) => {
      Androidlib.block(domains);
      refresh();
    },
    [refresh],
  );

  const unblock = useCallback(
    (password: string, domains: string[]) => {
      const ok = Androidlib.unblock(password, domains);
      refresh();
      return ok;
    },
    [refresh],
  );

  return {
    blocked,
    serviceEnabled,
    block,
    unblock,
    unlockPassword: Androidlib.getUnlockPassword,
    openAccessibilitySettings: Androidlib.openAccessibilitySettings,
  };
}

export type Blocker = ReturnType<typeof useBlocker>;
