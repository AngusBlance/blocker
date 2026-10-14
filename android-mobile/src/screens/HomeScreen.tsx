import { SITES, isSiteBlocked } from '../sites';
import { colors } from '../theme';
import { Button, Field, Muted, Pane } from '../ui';
import type { Blocker } from '../useBlocker';
import type { Tab } from '../../App';

export function HomeScreen({ blocker, go }: { blocker: Blocker; go: (tab: Tab) => void }) {
  const blockedSites = SITES.filter((s) => isSiteBlocked(s, blocker.blocked));

  return (
    <>
      {!blocker.serviceEnabled && (
        <Pane title="Service off" tone="error">
          <Muted>Sites won't be blocked until Blocker is on in Accessibility settings.</Muted>
          <Button title="set up" onPress={() => go('settings')} />
        </Pane>
      )}
      <Pane title="Status" focused>
        <Field
          label="state"
          value={blockedSites.length ? 'BLOCKED' : 'not blocked'}
          color={blockedSites.length ? colors.accent : undefined}
        />
        <Field
          label="service"
          value={blocker.serviceEnabled ? 'running' : 'NOT RUNNING'}
          color={blocker.serviceEnabled ? colors.success : colors.error}
        />
        <Field label="sites" value={`${SITES.length} sites, ${blockedSites.length} blocked`} />
      </Pane>
      <Button primary title="choose sites" onPress={() => go('sites')} />
    </>
  );
}
