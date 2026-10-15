import 'package:flutter/material.dart';

import '../blocker.dart';
import '../sites.dart';
import '../theme.dart';
import '../ui.dart';
import 'block_now_sheet.dart';
import 'setup_steps.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key, required this.blocker, required this.goToSites});

  final Blocker blocker;
  final VoidCallback goToSites;

  @override
  Widget build(BuildContext context) {
    final blocked = blocker.blockedSites;
    final scheduled = blocker.scheduledSites;
    final until = blocker.scheduledUntil;
    final anything = blocked.isNotEmpty || scheduled.isNotEmpty;
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
              anything ? 'BLOCKED' : 'not blocked',
              color: anything ? AppColors.accent : AppColors.foreground,
            ),
            if (until != null)
              Field(
                'now',
                'blocking ${scheduled.length} ${scheduled.length == 1 ? 'site' : 'sites'}'
                    ' · ends ${formatUntil(until, blocker.now())}',
                color: AppColors.accent,
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
        AppButton(
          'start a block',
          key: const Key('open-block-now'),
          primary: true,
          onPressed: () => showModalBottomSheet<void>(
            context: context,
            isScrollControlled: true,
            backgroundColor: AppColors.background,
            shape: const RoundedRectangleBorder(
              side: BorderSide(color: AppColors.accent),
            ),
            builder: (_) =>
                BlockNowSheet(now: blocker.now, onStart: blocker.blockNow),
          ),
        ),
        const SizedBox(height: 12),
        AppButton('choose sites', onPressed: goToSites),
      ],
    );
  }
}
