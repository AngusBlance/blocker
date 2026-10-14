import 'package:flutter/widgets.dart';

import 'backend.dart';
import 'sites.dart';

/// App state over androidlib. State lives natively; this re-reads it after
/// each change and whenever the app comes back to the foreground (e.g.
/// returning from the Accessibility settings screen).
class Blocker extends ChangeNotifier with WidgetsBindingObserver {
  Blocker(this.backend) {
    WidgetsBinding.instance.addObserver(this);
  }

  final Backend backend;

  List<String> domains = [];
  List<String> apps = [];
  bool serviceEnabled = false;
  int sdkInt = 0;
  bool loaded = false;

  /// Android 13+ locks accessibility for apps installed outside the Play
  /// Store ("restricted settings").
  bool get hasRestrictedSettings => sdkInt >= 33;

  bool isBlocked(Site site) =>
      site.domains.every(domains.contains) && site.apps.every(apps.contains);

  List<Site> get blockedSites => sites.where(isBlocked).toList();

  Future<void> load() async {
    sdkInt = await backend.sdkInt();
    await _blockMissingApps();
    await refresh();
  }

  /// Sites blocked before app blocking existed have their domains but not
  /// their apps; block the apps too so they stay fully blocked.
  Future<void> _blockMissingApps() async {
    final blocked = await backend.blockedDomains();
    final missing = sites
        .where((s) => s.domains.every(blocked.contains))
        .expand((s) => s.apps)
        .toList();
    if (missing.isNotEmpty) await backend.block([], missing);
  }

  Future<void> refresh() async {
    domains = await backend.blockedDomains();
    apps = await backend.blockedApps();
    serviceEnabled = await backend.isServiceEnabled();
    loaded = true;
    notifyListeners();
  }

  Future<void> block(List<Site> toBlock) async {
    await backend.block(
      toBlock.expand((s) => s.domains).toList(),
      toBlock.expand((s) => s.apps).toList(),
    );
    await refresh();
  }

  Future<bool> unblock(String password, List<Site> toUnblock) async {
    final ok = await backend.unblock(
      password,
      toUnblock.expand((s) => s.domains).toList(),
      toUnblock.expand((s) => s.apps).toList(),
    );
    await refresh();
    return ok;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) refresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}
