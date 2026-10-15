import 'package:flutter/material.dart';

import '../blocker.dart';
import '../ui.dart';

/// The steps to do in Android's settings, each with a button that goes
/// there. Shown on the dashboard and the settings tab while the service is
/// off. Android 13+ locks accessibility for apps installed outside the Play
/// Store, so step 1 unlocks it in App info before step 2 turns Blocker on.
/// Google Play
/// requires the disclosure, with an explicit agree step, before sending the
/// user to enable an accessibility service.
class SetupSteps extends StatelessWidget {
  const SetupSteps({super.key, required this.blocker});

  final Blocker blocker;

  @override
  Widget build(BuildContext context) {
    final restricted = blocker.hasRestrictedSettings;
    var n = 0;
    return Column(
      children: [
        const Pane(
          title: 'Before you start',
          children: [
            Muted(
              "Blocker needs one permission: Android's Accessibility service. It reads the web "
              'address in your browser and which app is open, and checks them against your block '
              "list on this phone only. Nothing is sent anywhere. It doesn't read passwords, "
              "messages or what's inside other apps.",
            ),
            Muted(
              "Android doesn't let apps ask for it with a popup, so the buttons below take you to "
              'each settings page. Tapping them means you agree.',
            ),
          ],
        ),
        if (restricted) ...[
          const SizedBox(height: 12),
          Pane(
            title: '${++n}. Allow restricted settings',
            focused: true,
            children: [
              const PathBox('App info › ⋮ › Allow restricted settings'),
              Muted(
                "Android locks Blocker because it wasn't installed from the Play Store, and step "
                '${n + 1} stays greyed out until this is done. ⋮ is in the top right corner; '
                'confirm with your PIN or fingerprint.',
              ),
              const Muted(
                'no "Allow restricted settings" in the ⋮ menu? some phones only show it after one '
                'try: open accessibility, tap Blocker, tap OK on the "Restricted setting" message, '
                'then come back here.',
              ),
              AppButton(
                'open app info',
                primary: true,
                onPressed: blocker.backend.openAppInfo,
              ),
              AppButton(
                'open accessibility',
                onPressed: blocker.backend.openAccessibilitySettings,
              ),
            ],
          ),
        ],
        const SizedBox(height: 12),
        Pane(
          title: '${++n}. Turn on Blocker',
          focused: true,
          children: [
            const PathBox('Accessibility › Blocker › Use Blocker › Allow'),
            const Muted(
              'Blocker may be under "Downloaded apps" or "Installed apps". then come back here; '
              'this page changes to "All set" once it\'s on.',
            ),
            AppButton(
              'agree and open accessibility',
              primary: true,
              onPressed: blocker.backend.openAccessibilitySettings,
            ),
          ],
        ),
      ],
    );
  }
}
