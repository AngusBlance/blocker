import { Pressable, StyleSheet, View } from 'react-native';

import { SITES, Site, isSiteBlocked } from '../sites';
import { colors } from '../theme';
import { Mono, Muted, Pane } from '../ui';
import type { Blocker } from '../useBlocker';

export function SitesScreen({
  blocker,
  requestUnlock,
}: {
  blocker: Blocker;
  requestUnlock: (site: Site) => void;
}) {
  const blockedCount = SITES.filter((s) => isSiteBlocked(s, blocker.blocked)).length;

  function toggle(site: Site) {
    if (isSiteBlocked(site, blocker.blocked)) requestUnlock(site);
    else blocker.block(site.domains);
  }

  return (
    <Pane title="Blocked sites" focused>
      <Muted>
        {SITES.length} sites, {blockedCount} blocked
      </Muted>
      <View>
        {SITES.map((site) => {
          const on = isSiteBlocked(site, blocker.blocked);
          return (
            <Pressable
              key={site.name}
              onPress={() => toggle(site)}
              style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
              <Mono style={on ? styles.on : styles.off}>{on ? '(x)' : '( )'}</Mono>
              <View style={styles.meta}>
                <Mono>{site.name}</Mono>
                <Mono style={styles.domains}>{site.domains.join(', ')}</Mono>
              </View>
            </Pressable>
          );
        })}
      </View>
      <Muted>tap to block. unblocking needs the password.</Muted>
    </Pane>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  pressed: { backgroundColor: colors.surface },
  on: { color: colors.accent, fontWeight: '700' },
  off: { color: colors.muted },
  meta: { flex: 1, gap: 2 },
  domains: { fontSize: 12, color: colors.muted },
});
