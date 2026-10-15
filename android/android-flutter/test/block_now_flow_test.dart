import 'package:blocker_flutter/schedule.dart';
import 'package:blocker_flutter/sites.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

final now = DateTime(2026, 10, 15, 13, 30);

Future<void> tapKey(WidgetTester tester, String key) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'pick sites, 1h, start: saves a one-off block and the dashboard says so',
    (tester) async {
      final backend = await pump(tester, clock: () => now);
      expect(find.textContaining(' · until '), findsNothing);

      await tapKey(tester, 'open-block-now');
      for (final s in sites.skip(2)) {
        await tapKey(tester, 'pick-${s.name}');
      }
      await tapKey(tester, 'length-1h');
      await tapKey(tester, 'start-block');

      final saved = backend.savedSchedules.single;
      expect(saved.sites, [sites[0].name, sites[1].name]);
      expect(saved.domains, [...sites[0].domains, ...sites[1].domains]);
      expect(saved.apps, [...sites[0].apps, ...sites[1].apps]);
      expect(
        saved.plan,
        ForPlan(startsAt: now, endsAt: DateTime(2026, 10, 15, 14, 30)),
      );
      expect(saved.action, const BlockAction());

      expect(
        find.byKey(const Key('start-block')),
        findsNothing,
      ); // sheet closed
      expect(find.text('Block now · 2 sites · until 14:30'), findsOneWidget);
      expect(find.text('BLOCKED'), findsOneWidget);
    },
  );

  testWidgets('until 7am in the evening says tomorrow', (tester) async {
    await pump(tester, clock: () => DateTime(2026, 10, 15, 22));
    await tapKey(tester, 'open-block-now');
    await tapKey(tester, 'length-until 7am');
    await tapKey(tester, 'start-block');
    expect(
      find.text('Block now · ${sites.length} sites · until tomorrow 07:00'),
      findsOneWidget,
    );
  });

  testWidgets(
    'a second block stacks on the first, and finished one-offs are tidied away',
    (tester) async {
      final backend = FakeBackend();
      final finished = Schedule(
        id: 'old',
        name: 'Block now',
        sites: ['Netflix'],
        domains: ['netflix.com'],
        apps: [],
        plan: ForPlan(
          startsAt: now.subtract(const Duration(hours: 3)),
          endsAt: now.subtract(const Duration(hours: 2)),
        ),
      );
      final weekly = Schedule(
        id: 'work',
        name: 'Work',
        sites: ['YouTube'],
        domains: ['youtube.com'],
        apps: [],
        plan: EveryPlan(days: {1, 2, 3, 4, 5}, start: 540, end: 1020),
      );
      backend.savedSchedules = [finished, weekly];
      await pump(tester, backend: backend, clock: () => now);

      await tapKey(tester, 'open-block-now');
      await tapKey(tester, 'length-30m');
      await tapKey(tester, 'start-block');
      await tapKey(tester, 'open-block-now');
      await tapKey(tester, 'length-2h');
      await tapKey(tester, 'start-block');

      final ids = [for (final s in backend.savedSchedules) s.id];
      expect(ids, isNot(contains('old')));
      expect(ids, contains('work')); // recurring schedules are never tidied
      final oneOffs = backend.savedSchedules
          .where((s) => s.plan is ForPlan)
          .toList();
      expect(oneOffs, hasLength(2)); // stacked, not replaced
      // One row each, soonest first. 15 Oct 2026 is a Thursday, so Work
      // (weekdays 9-5) is running too.
      final rows = tester
          .widgetList<Text>(find.textContaining(' · until '))
          .map((t) => t.data)
          .toList();
      expect(rows, [
        'Block now · ${sites.length} sites · until 14:00',
        'Block now · ${sites.length} sites · until 15:30',
        'Work · 1 site · until 17:00',
      ]);
    },
  );

  testWidgets('a failed start keeps the sheet open with the error', (
    tester,
  ) async {
    final backend = FakeBackend();
    final focus = Schedule(
      id: 'focus',
      name: 'Focus',
      sites: ['YouTube'],
      domains: ['youtube.com'],
      apps: [],
      plan: ForPlan(
        startsAt: now.subtract(const Duration(minutes: 5)),
        endsAt: now.add(const Duration(hours: 1)),
      ),
    );
    // Two stored schedules with one id can't happen for real, but re-saving
    // them is the simplest way to make the save fail.
    backend.savedSchedules = [focus, focus];
    await pump(tester, backend: backend, clock: () => now);
    await tapKey(tester, 'open-block-now');
    await tapKey(tester, 'start-block');
    expect(find.byKey(const Key('block-error')), findsOneWidget);
    expect(find.byKey(const Key('start-block')), findsOneWidget); // still open
  });

  testWidgets('the dashboard updates by itself when a block ends', (
    tester,
  ) async {
    var clock = now;
    final backend = await pump(tester, clock: () => clock);
    await tapKey(tester, 'open-block-now');
    await tapKey(tester, 'length-15m');
    await tapKey(tester, 'start-block');
    expect(
      find.text('Block now · ${sites.length} sites · until 13:45'),
      findsOneWidget,
    );
    clock = now.add(const Duration(minutes: 16));
    backend.clock = () => clock;
    await tester.pump(const Duration(minutes: 1));
    await tester.pumpAndSettle();
    expect(find.textContaining(' · until '), findsNothing);
  });
}
