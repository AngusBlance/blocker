import 'package:blocker_flutter/blocker.dart';
import 'package:blocker_flutter/schedule.dart';
import 'package:blocker_flutter/screens/schedules_screen.dart';
import 'package:blocker_flutter/sites.dart';
import 'package:blocker_flutter/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

final now = DateTime(2026, 10, 15, 13, 30); // a Thursday

Schedule every(
  String id,
  Set<int> days,
  int start,
  int end, {
  bool enabled = true,
}) => Schedule(
  id: id,
  name: id[0].toUpperCase() + id.substring(1),
  sites: ['YouTube'],
  domains: sites.first.domains,
  apps: sites.first.apps,
  plan: EveryPlan(days: days, start: start, end: end),
  enabled: enabled,
);

final work = every('work', {1, 2, 3, 4, 5}, 540, 1020); // running now
final evening = every('evening', {1, 2, 3, 4, 5, 6, 7}, 1080, 1380); // not yet
final gym = every('gym', {6}, 480, 540, enabled: false);

/// Owns the Blocker like the real app does, so its refresh timer is
/// cancelled when the test's widget tree goes away.
class _Host extends StatefulWidget {
  const _Host({required this.backend, required this.pickTime});

  final FakeBackend backend;
  final Future<TimeOfDay?> Function(BuildContext, TimeOfDay) pickTime;

  @override
  State<_Host> createState() => _HostState();
}

class _HostState extends State<_Host> {
  late final Blocker blocker = Blocker(widget.backend, clock: () => now)
    ..load();

  @override
  void dispose() {
    blocker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    theme: buildTheme(),
    home: Scaffold(
      body: ListenableBuilder(
        listenable: blocker,
        builder: (context, _) => SingleChildScrollView(
          child: SchedulesScreen(blocker: blocker, pickTime: widget.pickTime),
        ),
      ),
    ),
  );
}

Future<FakeBackend> pumpSchedules(
  WidgetTester tester, {
  List<TimeOfDay> picks = const [],
}) async {
  final backend = FakeBackend()
    ..clock = (() => now)
    ..savedSchedules = [work, evening, gym];
  final queue = [...picks];
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.6;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    _Host(
      backend: backend,
      pickTime: (context, initial) async =>
          queue.isEmpty ? null : queue.removeAt(0),
    ),
  );
  await tester.pumpAndSettle();
  return backend;
}

Future<void> tapKey(WidgetTester tester, String key) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
}

String status(WidgetTester tester, String id) =>
    tester.widget<Text>(find.byKey(Key('status-$id'))).data!;

Future<void> typePassword(WidgetTester tester) async {
  await tester.enterText(find.byKey(const Key('unlock-input')), password);
  await tapKey(tester, 'unlock-button');
}

void main() {
  testWidgets('each schedule shows its days, times, sites and state', (
    tester,
  ) async {
    await pumpSchedules(tester);
    expect(find.text('weekdays · 09:00–17:00'), findsOneWidget);
    expect(find.text('every day · 18:00–23:00'), findsOneWidget);
    expect(status(tester, 'work'), 'running · until 17:00');
    expect(status(tester, 'evening'), 'on');
    expect(status(tester, 'gym'), 'off');
    expect(find.byKey(const Key('end-work')), findsOneWidget);
    expect(find.byKey(const Key('end-evening')), findsNothing);
  });

  testWidgets('the switch turns a schedule off without deleting it', (
    tester,
  ) async {
    final backend = await pumpSchedules(tester);
    await tapKey(tester, 'toggle-evening');
    expect(backend.savedSchedules.map((s) => s.id), ['work', 'evening', 'gym']);
    expect(backend.savedSchedules[1].enabled, isFalse);
    expect(status(tester, 'evening'), 'off');
    await tapKey(tester, 'toggle-evening');
    expect(backend.savedSchedules[1].enabled, isTrue);
  });

  testWidgets(
    'turning off a running schedule asks for the password; cancel keeps it',
    (tester) async {
      final backend = await pumpSchedules(tester);
      await tapKey(tester, 'toggle-work');
      expect(find.text('WORK IS RUNNING'), findsOneWidget);
      await tapKey(tester, 'password-cancel');
      expect(backend.savedSchedules.first.enabled, isTrue);

      await tapKey(tester, 'toggle-work');
      await typePassword(tester);
      expect(backend.savedSchedules.first.enabled, isFalse);
      expect(status(tester, 'work'), 'off');
    },
  );

  testWidgets(
    'ending early needs the password and pauses only this occurrence',
    (tester) async {
      final backend = await pumpSchedules(tester);
      await tapKey(tester, 'end-work');
      await typePassword(tester);
      expect(backend.savedSchedules.first.enabled, isTrue); // still on
      expect(
        backend.savedSchedules.first.pausedUntil,
        DateTime(2026, 10, 15, 17),
      );
      expect(status(tester, 'work'), 'ended early · back after 17:00');
    },
  );

  testWidgets('editing days and times from the list saves the right plan', (
    tester,
  ) async {
    final backend = await pumpSchedules(
      tester,
      picks: [
        const TimeOfDay(hour: 22, minute: 0),
        const TimeOfDay(hour: 6, minute: 30),
      ],
    );
    await tapKey(tester, 'schedule-evening');
    await tapKey(tester, 'days-weekends');
    await tapKey(tester, 'time-from');
    await tapKey(tester, 'time-to');
    await tapKey(tester, 'save-schedule');
    expect(
      backend.savedSchedules[1].plan,
      EveryPlan(days: {6, 7}, start: 1320, end: 390),
    );
    expect(
      find.text('weekends · 22:00–06:30 next day'),
      findsOneWidget,
    ); // back on the list
  });

  testWidgets('a new schedule from a preset appears in the list', (
    tester,
  ) async {
    final backend = await pumpSchedules(tester);
    await tapKey(tester, 'new-schedule');
    await tapKey(tester, 'preset-bedtime');
    await tapKey(tester, 'site-chip-TikTok');
    await tapKey(tester, 'save-schedule');
    expect(backend.savedSchedules, hasLength(4));
    final added = backend.savedSchedules.last;
    expect(added.name, 'bedtime');
    expect(added.sites, ['TikTok']);
    expect(find.text('M T W T S · 22:00–07:00 next day'), findsOneWidget);
  });

  testWidgets('deleting a running schedule needs the password', (tester) async {
    final backend = await pumpSchedules(tester);
    await tapKey(tester, 'schedule-work');
    await tapKey(tester, 'delete-schedule');
    expect(find.text('WORK IS RUNNING'), findsOneWidget);
    await typePassword(tester);
    expect(backend.savedSchedules.map((s) => s.id), ['evening', 'gym']);
    expect(find.byKey(const Key('schedule-work')), findsNothing);
  });

  testWidgets(
    'shrinking a running schedule while editing asks for the password',
    (tester) async {
      final backend = await pumpSchedules(tester);
      await tapKey(tester, 'schedule-work');
      await tapKey(tester, 'day-4'); // drop Thursday, today
      await tapKey(tester, 'save-schedule');
      expect(find.text('WORK IS RUNNING'), findsOneWidget);
      await tapKey(tester, 'password-cancel');
      expect((backend.savedSchedules.first.plan as EveryPlan).days, {
        1,
        2,
        3,
        4,
        5,
      });
    },
  );
}
