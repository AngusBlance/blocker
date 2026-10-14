import { SetupSteps } from '../SetupSteps';
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
        <>
          <Pane title="Not blocking yet" tone="error">
            <Muted>nothing gets blocked until you do the steps below.</Muted>
          </Pane>
          <SetupSteps blocker={blocker} />
        </>
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
