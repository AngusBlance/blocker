import { Platform, StyleSheet } from 'react-native';

import { colors } from './theme';
import { Button, Mono, Muted, Pane } from './ui';
import type { Blocker } from './useBlocker';

// Android 13+ locks accessibility for apps installed outside the Play Store
// ("restricted settings"). The app can't reliably tell whether it's locked,
// so step 2 is always shown as "only if greyed out".
const HAS_RESTRICTED_SETTINGS = Platform.OS === 'android' && Platform.Version >= 33;

// The two things to do in Android's settings, each with a button that goes
// there. Shown on the dashboard and the settings tab while the service is
// off. Google Play requires the disclosure in step 1, with an explicit agree
// step, before sending the user to enable an accessibility service.
export function SetupSteps({ blocker }: { blocker: Blocker }) {
  return (
    <>
      <Pane title="1. Turn on Blocker" focused>
        <Path>Accessibility › Blocker › Use Blocker › Allow</Path>
        <Muted>
          the only permission Blocker needs. Android doesn't let apps ask for it with a popup, so
          you switch it on yourself. Blocker may be under "Downloaded apps" or "Installed apps".
        </Muted>
        <Muted>
          it reads the web address in your browser and which app is open, and checks them against
          your block list on this phone only. Nothing is sent anywhere. It doesn't read passwords,
          messages or what's inside other apps.
        </Muted>
        <Button
          primary
          title="agree and open accessibility"
          onPress={blocker.openAccessibilitySettings}
        />
      </Pane>

      {HAS_RESTRICTED_SETTINGS && (
        <Pane title="2. Only if Blocker is greyed out">
          <Path>App info › ⋮ › Allow restricted settings</Path>
          <Muted>
            Android locks this for apps not installed from the Play Store. Tap OK on the "denied
            access" or "Restricted setting" message first (the ⋮ option only shows up after
            that), then unlock it here, confirm with your PIN, and do step 1 again.
          </Muted>
          <Button title="open app info" onPress={blocker.openAppInfo} />
        </Pane>
      )}
    </>
  );
}

// The settings path to follow, highlighted like the TUI's accent text.
function Path({ children }: { children: string }) {
  return <Mono style={styles.path}>{children}</Mono>;
}

const styles = StyleSheet.create({
  path: {
    color: colors.accent,
    fontWeight: '700',
    backgroundColor: colors.surface,
    padding: 10,
    lineHeight: 20,
  },
});
