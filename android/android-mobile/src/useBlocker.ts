import Androidlib from 'androidlib';
import { useCallback, useEffect, useState } from 'react';
import { AppState } from 'react-native';

import { Blocked, SITES, Site } from './sites';

function readBlocked(): Blocked {
  return { domains: Androidlib.getBlockedDomains(), apps: Androidlib.getBlockedApps() };
}

// Sites blocked before app blocking existed have their domains but not their
// apps; block the apps too so they stay fully blocked.
function blockMissingApps() {
  const domains = Androidlib.getBlockedDomains();
  const apps = SITES.filter((s) => s.domains.every((d) => domains.includes(d))).flatMap(
    (s) => s.apps,
  );
  Androidlib.block([], apps);
}

// Thin React wrapper over androidlib. State lives natively; this just re-reads
// it after each change and whenever the app comes back to the foreground
// (e.g. returning from the Accessibility settings screen).
export function useBlocker() {
  const [blocked, setBlocked] = useState<Blocked>(() => {
    blockMissingApps();
    return readBlocked();
  });
  const [serviceEnabled, setServiceEnabled] = useState(() => Androidlib.isServiceEnabled());

  const refresh = useCallback(() => {
    setBlocked(readBlocked());
    setServiceEnabled(Androidlib.isServiceEnabled());
  }, []);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });
    return () => sub.remove();
  }, [refresh]);

  const block = useCallback(
    (sites: Site[]) => {
      Androidlib.block(
        sites.flatMap((s) => s.domains),
        sites.flatMap((s) => s.apps),
      );
      refresh();
    },
    [refresh],
  );

  const unblock = useCallback(
    (password: string, sites: Site[]) => {
      const ok = Androidlib.unblock(
        password,
        sites.flatMap((s) => s.domains),
        sites.flatMap((s) => s.apps),
      );
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
    unlockPassword: () => Androidlib.getUnlockPassword(),
    // Wrapped so a press event passed by onPress never reaches the native
    // function, which rejects extra arguments.
    openAccessibilitySettings: () => Androidlib.openAccessibilitySettings(),
    openAppInfo: () => Androidlib.openAppInfo(),
  };
}

export type Blocker = ReturnType<typeof useBlocker>;
