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
    final anything = blocked.isNotEmpty || blocker.running.isNotEmpty;
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
            for (final (i, row) in blocker.runningRows.indexed)
              Field(
                i == 0 ? 'now' : '',
                '${row.name} · ${row.siteCount} ${row.siteCount == 1 ? 'site' : 'sites'}'
                ' · until ${formatUntil(row.until, blocker.now())}',
                color: AppColors.accent,
              ),
            Field(
              'service',
              blocker.serviceEnabled ? 'running' : 'NOT RUNNING',
              color: blocker.serviceEnabled
                  ? AppColors.success
                  : AppColors.error,
            ),
            Field('manual', '${blocked.length} of ${sites.length} sites'),
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
            showDragHandle: true,
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
