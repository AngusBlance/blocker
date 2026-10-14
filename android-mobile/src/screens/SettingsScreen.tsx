import { colors } from '../theme';
import { Button, Field, Muted, Pane } from '../ui';
import type { Blocker } from '../useBlocker';

// Google Play requires this disclosure, with an explicit agree step, before
// sending the user to enable an accessibility service.
export function SettingsScreen({ blocker }: { blocker: Blocker }) {
  if (blocker.serviceEnabled) {
    return (
      <Pane title="Accessibility service" focused>
        <Field label="service" value="running" color={colors.success} />
        <Muted>to turn it off: Android Settings › Accessibility › Blocker.</Muted>
      </Pane>
    );
  }

  return (
    <Pane title="Before you turn it on" focused>
      <Muted>
        Blocker uses Android's Accessibility service to read the web address in your browser. It
        checks that address against your block list, on this phone only. Nothing is sent anywhere.
      </Muted>
      <Muted>It doesn't read passwords, messages or other apps.</Muted>
      <Button primary title="agree and open settings" onPress={blocker.openAccessibilitySettings} />
    </Pane>
  );
}
