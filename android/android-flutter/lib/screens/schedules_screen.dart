import 'package:flutter/material.dart';

import '../backend.dart';
import '../blocker.dart';
import '../schedule.dart';
import '../schedule_format.dart';
import '../theme.dart';
import '../ui.dart';
import 'password_entry.dart';
import 'schedule_editor.dart';

/// Recurring schedules (and any running one-off blocks), each with an on/off
/// switch; running ones can be ended early with the unlock password. Tap a
/// recurring one to edit it.
class SchedulesScreen extends StatelessWidget {
  const SchedulesScreen({
    super.key,
    required this.blocker,
    this.pickTime = systemTimePicker,
  });

  final Blocker blocker;
  final TimePicker pickTime;

  static void _say(BuildContext context, String message) {
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message, style: monoStyle())));
  }

  /// Runs [action]; if androidlib refuses because a schedule is running,
  /// asks for the unlock password and tries once more with it. Any other
  /// failure is shown rather than swallowed. True if it went through.
  Future<bool> _guarded(
    BuildContext context,
    String name,
    Future<void> Function(String? password) action,
  ) async {
    try {
      try {
        await action(null);
        return true;
      } on ScheduleLockedException {
        if (!context.mounted) return false;
        final typed = await askForUnlockPassword(
          context,
          password: blocker.backend.unlockPassword,
          title: '$name is running',
          reason: 'changing a running schedule needs the unlock password.',
          actionLabel: 'change it',
        );
        if (typed == null) return false;
        await action(typed);
        return true;
      }
    } catch (e) {
      if (context.mounted) _say(context, "couldn't save: $e");
      return false;
    }
  }

  Future<void> _endEarly(BuildContext context, Schedule s) async {
    final typed = await askForUnlockPassword(
      context,
      password: blocker.backend.unlockPassword,
      title: 'End ${s.name} early',
      reason: s.plan is EveryPlan
          ? 'this ends it until next time; it comes back as scheduled.'
          : 'this ends the block now.',
      actionLabel: 'end it',
    );
    if (typed == null || !context.mounted) return;
    try {
      final result = await blocker.endEarly(s.id, typed);
      if (!context.mounted) return;
      _say(context, switch (result) {
        PauseResult.paused => '${s.name} ended early.',
        PauseResult.notRunning => '${s.name} had already finished.',
        PauseResult.wrongPassword => "that password didn't match.",
      });
    } catch (e) {
      if (context.mounted) _say(context, "couldn't end it: $e");
    }
  }

  Future<bool> _confirmDelete(BuildContext context, Schedule s) async =>
      await showDialog<bool>(
        context: context,
        builder: (dialog) => AlertDialog(
          backgroundColor: AppColors.surface,
          shape: const RoundedRectangleBorder(
            side: BorderSide(color: AppColors.accent),
          ),
          title: Text('delete ${s.name}?', style: monoStyle(bold: true)),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialog).pop(false),
              child: Text('keep it', style: monoStyle()),
            ),
            TextButton(
              key: const Key('confirm-delete'),
              onPressed: () => Navigator.of(dialog).pop(true),
              child: Text(
                'delete',
                style: monoStyle(color: AppColors.error, bold: true),
              ),
            ),
          ],
        ),
      ) ??
      false;

  Future<void> _openEditor(BuildContext context, {Schedule? initial}) =>
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (route) => PushedPage(
            scroll: false,
            child: ScheduleEditor(
              initial: initial,
              newId: () => newScheduleId('schedule'),
              pickTime: pickTime,
              onSave: (schedule) async {
                final saved = await _guarded(
                  route,
                  initial?.name ?? schedule.name,
                  (password) =>
                      blocker.saveSchedule(schedule, password: password),
                );
                if (saved && route.mounted) Navigator.of(route).pop();
              },
              onDelete: initial == null
                  ? null
                  : () async {
                      // A running one asks for the password instead (via
                      // _guarded), which is confirmation enough.
                      if (!blocker.isRunning(initial.id) &&
                          !await _confirmDelete(route, initial)) {
                        return;
                      }
                      if (!route.mounted) return;
                      final deleted = await _guarded(
                        route,
                        initial.name,
                        (password) => blocker.deleteSchedule(
                          initial.id,
                          password: password,
                        ),
                      );
                      if (deleted && route.mounted) Navigator.of(route).pop();
                    },
            ),
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final now = blocker.now();
    final shown = [
      for (final s in blocker.schedules)
        // Finished one-offs are history, not schedules.
        if (s.plan is EveryPlan || blocker.isRunning(s.id)) s,
    ];
    return Column(
      children: [
        Pane(
          title: 'Schedules',
          focused: true,
          children: [
            if (shown.isEmpty)
              const Muted(
                'no schedules yet. a schedule blocks sites at set times, like weekdays 9–5 or every night.',
              ),
            for (final s in shown)
              _ScheduleCard(
                schedule: s,
                until: blocker.runningUntil(s.id),
                now: now,
                onTap: s.plan is EveryPlan
                    ? () => _openEditor(context, initial: s)
                    : null,
                onToggle: (on) => _guarded(
                  context,
                  s.name,
                  (password) => blocker.setEnabled(s, on, password: password),
                ),
                onEndEarly: () => _endEarly(context, s),
              ),
          ],
        ),
        const SizedBox(height: 12),
        AppButton(
          'new schedule',
          key: const Key('new-schedule'),
          primary: true,
          onPressed: () => _openEditor(context),
        ),
      ],
    );
  }
}

class _ScheduleCard extends StatelessWidget {
  const _ScheduleCard({
    required this.schedule,
    required this.until,
    required this.now,
    required this.onTap,
    required this.onToggle,
    required this.onEndEarly,
  });

  final Schedule schedule;

  /// When it stops, if it's running now.
  final DateTime? until;
  final DateTime now;
  final VoidCallback? onTap;
  final Future<void> Function(bool on) onToggle;
  final VoidCallback onEndEarly;

  @override
  Widget build(BuildContext context) {
    final s = schedule;
    final running = until != null;
    final paused =
        s.enabled && s.pausedUntil != null && now.isBefore(s.pausedUntil!);
    final plan = s.plan;
    final (status, statusColor) = switch ((s.enabled, running, paused)) {
      (false, _, _) => ('off', AppColors.muted),
      (_, true, _) => (
        'running · until ${formatUntil(until!, now)}',
        AppColors.accent,
      ),
      (_, _, true) => ('ended early · back next time', AppColors.muted),
      _ => ('on', AppColors.success),
    };
    return Material(
      key: Key('schedule-${s.id}'),
      color: AppColors.background,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: running ? AppColors.accent : AppColors.border),
      ),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(child: Text(s.name, style: monoStyle(bold: true))),
                  // One-off blocks just run out; "end early" is how to stop one.
                  if (plan is EveryPlan)
                    SquareChip(
                      s.enabled ? 'on' : 'off',
                      key: Key('toggle-${s.id}'),
                      marker: false,
                      selected: s.enabled,
                      onTap: () => onToggle(!s.enabled),
                    ),
                ],
              ),
              const SizedBox(height: 4),
              Text(switch (plan) {
                EveryPlan() => formatEvery(plan),
                ForPlan() => 'one-off block',
              }, style: monoStyle(color: AppColors.foreground)),
              Text(
                s.sites.join(', '),
                style: monoStyle(color: AppColors.muted, size: 12),
              ),
              const SizedBox(height: 4),
              Text(
                status,
                key: Key('status-${s.id}'),
                style: monoStyle(color: statusColor, size: 12),
              ),
              if (running) ...[
                const SizedBox(height: 8),
                AppButton(
                  'end early',
                  key: Key('end-${s.id}'),
                  onPressed: onEndEarly,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
