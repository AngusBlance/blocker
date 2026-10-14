import 'package:flutter/material.dart';

import '../blocker.dart';
import '../sites.dart';
import '../theme.dart';
import '../ui.dart';
import 'setup_steps.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key, required this.blocker, required this.goToSites});

  final Blocker blocker;
  final VoidCallback goToSites;

  @override
  Widget build(BuildContext context) {
    final blocked = blocker.blockedSites;
    return Column(
      children: [
        if (!blocker.serviceEnabled) ...[
          const Pane(
            title: 'Not blocking yet',
            error: true,
            children: [
              Muted('nothing gets blocked until you do the steps below.'),
            ],
          ),
          const SizedBox(height: 12),
          SetupSteps(blocker: blocker),
          const SizedBox(height: 12),
        ],
        Pane(
          title: 'Status',
          focused: true,
          children: [
            Field(
              'state',
              blocked.isNotEmpty ? 'BLOCKED' : 'not blocked',
              color: blocked.isNotEmpty
                  ? AppColors.accent
                  : AppColors.foreground,
            ),
            Field(
              'service',
              blocker.serviceEnabled ? 'running' : 'NOT RUNNING',
              color: blocker.serviceEnabled
                  ? AppColors.success
                  : AppColors.error,
            ),
            Field('sites', '${sites.length} sites, ${blocked.length} blocked'),
          ],
        ),
        const SizedBox(height: 12),
        AppButton('choose sites', primary: true, onPressed: goToSites),
      ],
    );
  }
}
