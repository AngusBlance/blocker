import { Platform, StyleSheet } from 'react-native';

import { colors } from './theme';
import { Button, Mono, Muted, Pane } from './ui';
import type { Blocker } from './useBlocker';

// Android 13+ locks accessibility for apps installed outside the Play Store
// ("restricted settings"), so it has to be unlocked before Blocker can be
// turned on. Its "Allow restricted settings" option only appears after the
// user has tapped the locked Blocker once, hence steps 1 and 2.
const HAS_RESTRICTED_SETTINGS = Platform.OS === 'android' && Platform.Version >= 33;

// The steps to do in Android's settings, each with a button that goes there.
// Shown on the dashboard and the settings tab while the service is off.
// Google Play requires the disclosure, with an explicit agree step, before
// sending the user to enable an accessibility service.
export function SetupSteps({ blocker }: { blocker: Blocker }) {
  let n = 0;

  return (
    <>
      <Pane title="Before you start">
        <Muted>
          Blocker needs one permission: Android's Accessibility service. It reads the web address in
          your browser and which app is open, and checks them against your block list on this phone
          only. Nothing is sent anywhere. It doesn't read passwords, messages or what's inside other
          apps.
        </Muted>
        <Muted>
          Android doesn't let apps ask for it with a popup, so the buttons below take you to each
          settings page. Tapping them means you agree.
        </Muted>
      </Pane>

      {HAS_RESTRICTED_SETTINGS && (
        <>
          <Pane title={`${++n}. Tap the greyed-out Blocker`} focused>
            <Path>Accessibility › Blocker › OK</Path>
            <Muted>
              Android locks Blocker because it wasn't installed from the Play Store. Tap it once and
              tap OK on the "denied access" or "Restricted setting" message. That makes the unlock
              option in the next step show up.
            </Muted>
            <Muted>
              not greyed out? skip to step {n + 2}. Blocker may be under "Downloaded apps" or
              "Installed apps".
            </Muted>
            <Button
              primary
              title="agree and open accessibility"
              onPress={blocker.openAccessibilitySettings}
            />
          </Pane>

          <Pane title={`${++n}. Allow restricted settings`} focused>
            <Path>App info › ⋮ › Allow restricted settings</Path>
            <Muted>⋮ is in the top right corner. Confirm with your PIN or fingerprint.</Muted>
            <Button primary title="open app info" onPress={blocker.openAppInfo} />
          </Pane>
        </>
      )}

      <Pane title={`${++n}. Turn on Blocker`} focused>
        <Path>Accessibility › Blocker › Use Blocker › Allow</Path>
        <Muted>then come back here. this page changes to "All set" once it's on.</Muted>
        <Button
          primary
          title={HAS_RESTRICTED_SETTINGS ? 'open accessibility' : 'agree and open accessibility'}
          onPress={blocker.openAccessibilitySettings}
        />
      </Pane>
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
