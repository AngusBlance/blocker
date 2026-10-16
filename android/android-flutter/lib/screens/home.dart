import 'package:flutter/material.dart';

import '../blocker.dart';
import '../sites.dart';
import '../theme.dart';
import '../ui.dart';
import '../focus.dart';
import 'block_now_sheet.dart';
import 'focus_sheet.dart';
import 'password_entry.dart';
import 'setup_steps.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key, required this.blocker, required this.goToSites});

  final Blocker blocker;
  final VoidCallback goToSites;

  @override
  Widget build(BuildContext context) {
    final blocked = blocker.blockedSites;
    final focus = blocker.focus;
    final anything =
        blocked.isNotEmpty || blocker.running.isNotEmpty || focus != null;
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
              focus != null
                  ? 'FOCUS'
                  : anything
                  ? 'BLOCKED'
                  : 'not blocked',
              color: anything ? AppColors.accent : AppColors.foreground,
            ),
            if (focus != null) ...[
              Field(
                'focus',
                'until ${formatUntil(focus.endsAt, blocker.now())}'
                    ' · ${formatRemaining(focus.endsAt.difference(blocker.now()))} left',
                color: AppColors.accent,
              ),
              Field('allows', _allowed(focus.sites, _extraApps(focus))),
            ],
            for (final (i, row) in blocker.runningRows.indexed)
              Field(
                i == 0 ? 'now' : '',
                '${row.name} · ${row.siteCount} ${row.siteCount == 1 ? 'site' : 'sites'}'
                ' · until ${formatUntil(row.until, blocker.now())}'
                ' · ${formatRemaining(row.until.difference(blocker.now()))} left',
                color: AppColors.accent,
              ),
            if (blocker.nextRow case final next?)
              Field(
                'next',
                '${next.name} · from ${formatUntil(next.at, blocker.now())}',
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
        if (focus == null)
          AppButton(
            'focus',
            key: const Key('open-focus'),
            onPressed: () => showModalBottomSheet<void>(
              context: context,
              isScrollControlled: true,
              showDragHandle: true,
              backgroundColor: AppColors.background,
              shape: const RoundedRectangleBorder(
                side: BorderSide(color: AppColors.accent),
              ),
              builder: (_) => FocusSheet(
                onStart: blocker.startFocus,
                loadApps: blocker.backend.installedApps,
              ),
            ),
          )
        else
          AppButton(
            'end focus early',
            key: const Key('end-focus'),
            onPressed: () => _endFocus(context),
          ),
        const SizedBox(height: 12),
        AppButton('choose sites', onPressed: goToSites),
      ],
    );
  }

  /// Allowed apps that aren't just an allowed site's own app.
  static int _extraApps(FocusSession focus) {
    final siteApps = {
      for (final s in sites)
        if (focus.sites.contains(s.name)) ...s.apps,
    };
    return focus.apps.where((a) => !siteApps.contains(a)).length;
  }

  /// "YouTube, Notion + 2 apps" (app names aren't stored, only packages).
  static String _allowed(List<String> siteNames, int appCount) {
    final apps = appCount == 0
        ? ''
        : '$appCount ${appCount == 1 ? 'app' : 'apps'}';
    if (siteNames.isEmpty) return apps;
    return [siteNames.join(', '), if (apps.isNotEmpty) apps].join(' + ');
  }

  Future<void> _endFocus(BuildContext context) async {
    final typed = await askForUnlockPassword(
      context,
      password: blocker.backend.unlockPassword,
      title: 'End focus early',
      reason: 'everything you blocked out comes back now.',
      actionLabel: 'end it',
    );
    if (typed == null || !context.mounted) return;
    final result = await blocker.endFocus(typed);
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(switch (result) {
          FocusEndResult.ended => 'focus ended.',
          FocusEndResult.notRunning => 'focus had already finished.',
          FocusEndResult.wrongPassword => "that password didn't match.",
        }, style: monoStyle()),
      ),
    );
  }
}
