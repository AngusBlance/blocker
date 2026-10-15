import 'package:flutter/material.dart';

import '../blocker.dart';
import '../ui.dart';

/// The steps to do in Android's settings, each with a button that goes
/// there. Shown on the dashboard and the settings tab while the service is
/// off. Android 13+ locks accessibility for apps installed outside the Play
/// Store, and its "Allow restricted settings" option only appears after the
/// locked Blocker has been tapped once, hence steps 1 and 2. Google Play
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
            title: '${++n}. Tap the greyed-out Blocker',
            focused: true,
            children: [
              const PathBox('Accessibility › Blocker › OK'),
              const Muted(
                "Android locks Blocker because it wasn't installed from the Play Store. Tap it "
                'once and tap OK on the "denied access" or "Restricted setting" message. That '
                'makes the unlock option in the next step show up.',
              ),
              Muted(
                'not greyed out? skip to step ${n + 2}. Blocker may be under "Downloaded apps" '
                'or "Installed apps".',
              ),
              AppButton(
                'agree and open accessibility',
                primary: true,
                onPressed: blocker.backend.openAccessibilitySettings,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Pane(
            title: '${++n}. Allow restricted settings',
            focused: true,
            children: [
              const PathBox('App info › ⋮ › Allow restricted settings'),
              const Muted(
                '⋮ is in the top right corner. Confirm with your PIN or fingerprint.',
              ),
              AppButton(
                'open app info',
                primary: true,
                onPressed: blocker.backend.openAppInfo,
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
              'then come back here. this page changes to "All set" once it\'s on.',
            ),
            AppButton(
              restricted
                  ? 'open accessibility'
                  : 'agree and open accessibility',
              primary: true,
              onPressed: blocker.backend.openAccessibilitySettings,
            ),
          ],
        ),
      ],
    );
  }
}
