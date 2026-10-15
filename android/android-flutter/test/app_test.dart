import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  testWidgets('dashboard shows status and no setup when the service is on', (
    tester,
  ) async {
    await pump(tester);
    expect(find.text('not blocked'), findsOneWidget);
    expect(find.text('running'), findsOneWidget);
    expect(find.text('NOT BLOCKING YET'), findsNothing);
  });

  testWidgets(
    'dashboard leads with the setup steps, unlocking first, when the service is off',
    (tester) async {
      final b = await pump(tester, backend: FakeBackend(serviceOn: false));
      expect(find.text('NOT BLOCKING YET'), findsOneWidget);
      expect(find.text('1. ALLOW RESTRICTED SETTINGS'), findsOneWidget);
      expect(find.text('2. TURN ON BLOCKER'), findsOneWidget);
      await tester.ensureVisible(find.text('open app info').first);
      await tester.tap(find.text('open app info').first);
      expect(b.appInfoOpened, 1);
    },
  );

  testWidgets('before Android 13 there is no restricted-settings step', (
    tester,
  ) async {
    await pump(tester, backend: FakeBackend(serviceOn: false, sdk: 32));
    expect(find.text('1. TURN ON BLOCKER'), findsOneWidget);
    expect(
      find.text('ALLOW RESTRICTED SETTINGS', findRichText: true),
      findsNothing,
    );
    final open = find.text('agree and open accessibility');
    await tester.ensureVisible(open);
    await tester.tap(open);
  });

  testWidgets('tapping a site blocks its domains and its app', (tester) async {
    final b = await pump(tester);
    await tapTab(tester, 'sites');
    await tester.tap(find.byKey(const Key('site-Netflix')));
    await tester.pumpAndSettle();
    expect(b.domains, {'netflix.com'});
    expect(b.apps, {'com.netflix.mediaclient'});
    expect(find.text('(x)'), findsOneWidget);
  });

  testWidgets('unblocking needs the full password typed', (tester) async {
    final b = await pump(tester);
    await tapTab(tester, 'sites');
    await tester.tap(find.byKey(const Key('site-YouTube')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('site-YouTube')));
    await tester.pumpAndSettle();
    expect(find.text('UNLOCK YOUTUBE'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('unlock-input')),
      'x' * password.length,
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('unlock-button')));
    await tester.pumpAndSettle();
    expect(find.text("that doesn't match."), findsOneWidget);
    expect(b.domains, contains('youtube.com'));

    await tester.enterText(find.byKey(const Key('unlock-input')), password);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('unlock-button')));
    await tester.pumpAndSettle();
    expect(b.domains, isEmpty);
    expect(b.apps, isEmpty);
    expect(find.text('BLOCKED SITES'), findsOneWidget); // back on the sites tab
  });

  testWidgets(
    'sites blocked before app blocking get their apps blocked on launch',
    (tester) async {
      final b = FakeBackend()
        ..domains.addAll(['youtube.com', 'googlevideo.com']);
      await pump(tester, backend: b);
      expect(b.apps, {'com.google.android.youtube'});
    },
  );

  testWidgets('unlocking opens as its own screen with a way back', (
    tester,
  ) async {
    final b = await pump(tester);
    await tapTab(tester, 'sites');
    await tester.tap(find.byKey(const Key('site-Netflix')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('site-Netflix')));
    await tester.pumpAndSettle();
    expect(find.text('UNLOCK NETFLIX'), findsOneWidget);
    await tester.tap(find.byKey(const Key('page-back')));
    await tester.pumpAndSettle();
    expect(find.text('BLOCKED SITES'), findsOneWidget);
    expect(b.domains, contains('netflix.com'));
  });

  testWidgets('unlock everything shows when several sites are blocked', (
    tester,
  ) async {
    final b = await pump(tester);
    await tapTab(tester, 'sites');
    expect(find.byKey(const Key('unlock-everything')), findsNothing);
    for (final name in ['Netflix', 'TikTok']) {
      await tester.tap(find.byKey(Key('site-$name')));
      await tester.pumpAndSettle();
    }
    await tester.ensureVisible(find.byKey(const Key('unlock-everything')));
    await tester.tap(find.byKey(const Key('unlock-everything')));
    await tester.pumpAndSettle();
    expect(find.text('UNLOCK EVERYTHING'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('unlock-input')), password);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('unlock-button')));
    await tester.pumpAndSettle();
    expect(b.domains, isEmpty);
    expect(find.text('BLOCKED SITES'), findsOneWidget);
  });

  testWidgets('the schedules tab is the third tile', (tester) async {
    await pump(tester);
    await tapTab(tester, 'schedules');
    expect(find.text('SCHEDULES'), findsOneWidget);
    expect(find.byKey(const Key('new-schedule')), findsOneWidget);
  });
}
