import { SetupSteps } from '../SetupSteps';
import { colors } from '../theme';
import { Button, Field, Muted, Pane } from '../ui';
import type { Blocker } from '../useBlocker';

// Re-checks itself when the user comes back from Android's settings.
export function SettingsScreen({ blocker }: { blocker: Blocker }) {
  return (
    <>
      {blocker.serviceEnabled ? (
        <Pane title="All set" focused>
          <Field label="service" value="running" color={colors.success} />
          <Muted>
            to check: block a site, then open it in your browser or open its app. you should get the
            block screen.
          </Muted>
          <Button title="open accessibility" onPress={blocker.openAccessibilitySettings} />
        </Pane>
      ) : (
        <SetupSteps blocker={blocker} />
      )}

      <Pane title="If blocking stops working">
        <Muted>
          some phones (Samsung, Xiaomi, OnePlus) shut down background services to save battery,
          which can switch Blocker off. In app info, set battery to Unrestricted (or turn off
          battery optimisation), then check Blocker is still on in Accessibility.
        </Muted>
        <Button title="open app info" onPress={blocker.openAppInfo} />
      </Pane>
    </>
  );
}
