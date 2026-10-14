import { ReactNode } from 'react';
import { Platform } from 'react-native';

import { colors } from '../theme';
import { Button, Field, Muted, Pane } from '../ui';
import type { Blocker } from '../useBlocker';

// Android 13+ locks accessibility for apps installed outside the Play Store
// ("restricted settings"). An app can't reliably tell whether it's locked, so
// step 2 is shown as "only if step 1 was greyed out".
const HAS_RESTRICTED_SETTINGS = Platform.OS === 'android' && Platform.Version >= 33;

// Setup checklist. Status re-checks itself when the user comes back from
// Android's settings. Google Play requires the disclosure in step 1, with an
// explicit agree step, before sending the user to enable an accessibility
// service.
export function SettingsScreen({ blocker }: { blocker: Blocker }) {
  const on = blocker.serviceEnabled;

  return (
    <>
      {on && (
        <Pane title="All set" focused>
          <Field label="service" value="running" color={colors.success} />
          <Muted>
            to check: block a site, then open it in your browser or open its app. you should get
            the block screen.
          </Muted>
        </Pane>
      )}

      <Step n={1} title="Turn on Blocker" status={on ? 'done' : 'to do'} focused={!on}>
        <Muted>
          Blocker uses Android's Accessibility service to read the web address in your browser and
          see which app is open. It checks those against your block list, on this phone only.
          Nothing is sent anywhere. It doesn't read passwords, messages or what's inside other
          apps.
        </Muted>
        {!on && (
          <Muted>
            {'a. tap the button below\n' +
              'b. if you land on a list, tap Blocker (it may be under "Downloaded apps" or ' +
              '"Installed apps")\n' +
              'c. turn on "Use Blocker" and tap Allow\n' +
              'd. come back here'}
          </Muted>
        )}
        {!on && HAS_RESTRICTED_SETTINGS && (
          <Muted>
            greyed out, or a "denied access" / "Restricted setting" message? tap OK, then do step
            2.
          </Muted>
        )}
        <Button
          primary={!on}
          title={on ? 'open accessibility' : 'agree and open accessibility'}
          onPress={blocker.openAccessibilitySettings}
        />
      </Step>

      {HAS_RESTRICTED_SETTINGS && !on && (
        <Step n={2} title="Only if step 1 was greyed out" status="if needed">
          <Muted>
            Android locks accessibility for apps installed from a browser instead of the Play
            Store. Unlock it once:
          </Muted>
          <Muted>
            {'a. tap "open app info" below\n' +
              'b. tap ⋮ in the top right corner\n' +
              'c. tap "Allow restricted settings" and confirm with your PIN or fingerprint\n' +
              'd. come back here and do step 1 again'}
          </Muted>
          <Muted>
            no "Allow restricted settings" in the ⋮ menu? Android only adds it after you've tried
            step 1 and seen the message, so do that first.
          </Muted>
          <Button title="open app info" onPress={blocker.openAppInfo} />
        </Step>
      )}

      <Pane title="If blocking stops working">
        <Muted>
          some phones (Samsung, Xiaomi, OnePlus) shut down background services to save battery,
          which can switch Blocker off. In app info, set battery to Unrestricted (or turn off
          battery optimisation), then check step 1 again.
        </Muted>
        <Button title="open app info" onPress={blocker.openAppInfo} />
      </Pane>
    </>
  );
}

function Step({
  n,
  title,
  status,
  focused,
  children,
}: {
  n: number;
  title: string;
  status: 'done' | 'to do' | 'if needed';
  focused?: boolean;
  children: ReactNode;
}) {
  const color =
    status === 'done' ? colors.success : status === 'to do' ? colors.accent : colors.muted;
  return (
    <Pane title={`${n}. ${title}`} focused={focused}>
      <Field label="status" value={status} color={color} />
      {children}
    </Pane>
  );
}
