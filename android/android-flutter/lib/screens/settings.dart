import 'package:flutter/material.dart';

import '../blocker.dart';
import '../theme.dart';
import '../ui.dart';
import 'setup_steps.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key, required this.blocker});

  final Blocker blocker;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        if (blocker.serviceEnabled)
          Pane(
            title: 'All set',
            focused: true,
            children: [
              const Field('service', 'running', color: AppColors.success),
              const Muted(
                'to check: block a site, then open it in your browser or open its app. you '
                'should get the block screen.',
              ),
              AppButton(
                'open accessibility',
                onPressed: blocker.backend.openAccessibilitySettings,
              ),
            ],
          )
        else
          SetupSteps(blocker: blocker),
        const SizedBox(height: 12),
        Pane(
          title: 'If blocking stops working',
          children: [
            const Muted(
              'some phones (Samsung, Xiaomi, OnePlus) shut down background services to save '
              'battery, which can switch Blocker off. In app info, set battery to Unrestricted '
              '(or turn off battery optimisation), then check Blocker is still on in '
              'Accessibility.',
            ),
            AppButton('open app info', onPressed: blocker.backend.openAppInfo),
          ],
        ),
      ],
    );
  }
}
