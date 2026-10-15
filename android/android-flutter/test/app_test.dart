import 'package:blocker_flutter/backend.dart';
import 'package:blocker_flutter/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const password = 'secret-unlock-password';

/// Stands in for androidlib: an in-memory block list.
class FakeBackend implements Backend {
  FakeBackend({this.serviceOn = true, this.sdk = 35});

  final Set<String> domains = {};
  final Set<String> apps = {};
  bool serviceOn;
  int sdk;
  int accessibilityOpened = 0;
  int appInfoOpened = 0;

  @override
  Future<List<String>> blockedDomains() async => domains.toList()..sort();

  @override
  Future<List<String>> blockedApps() async => apps.toList()..sort();

  @override
  Future<void> block(List<String> d, List<String> a) async {
    domains.addAll(d);
    apps.addAll(a);
  }

  @override
  Future<bool> unblock(String typed, List<String> d, List<String> a) async {
    if (typed != password) return false;
    domains.removeAll(d);
    apps.removeAll(a);
    return true;
  }

  @override
  Future<String> unlockPassword() async => password;

  @override
  Future<bool> isServiceEnabled() async => serviceOn;

  @override
  Future<int> sdkInt() async => sdk;

  @override
  Future<void> openAccessibilitySettings() async => accessibilityOpened++;

  @override
  Future<void> openAppInfo() async => appInfoOpened++;
}

Future<FakeBackend> pump(WidgetTester tester, {FakeBackend? backend}) async {
  final b = backend ?? FakeBackend();
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.6;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(BlockerApp(backend: b));
  await tester.pumpAndSettle();
  return b;
}

Future<void> tapTab(WidgetTester tester, String label) async {
  await tester.tap(find.byKey(Key('tab-$label')));
  await tester.pumpAndSettle();
}

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
    'dashboard leads with the three setup steps when the service is off',
    (tester) async {
      final b = await pump(tester, backend: FakeBackend(serviceOn: false));
      expect(find.text('NOT BLOCKING YET'), findsOneWidget);
      expect(find.text('1. TAP THE GREYED-OUT BLOCKER'), findsOneWidget);
      expect(find.text('2. ALLOW RESTRICTED SETTINGS'), findsOneWidget);
      expect(find.text('3. TURN ON BLOCKER'), findsOneWidget);
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
}
