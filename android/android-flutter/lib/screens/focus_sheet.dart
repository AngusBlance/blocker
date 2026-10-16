import 'package:flutter/material.dart';

import '../backend.dart';
import '../sites.dart';
import '../theme.dart';
import '../ui.dart';
import 'app_picker.dart';

const focusLengths = [
  Duration(minutes: 25),
  Duration(minutes: 50),
  Duration(hours: 1),
  Duration(hours: 2),
];

/// Focus mode: pick the few sites and apps you need, pick how long, start.
/// Everything else is blocked until it ends.
class FocusSheet extends StatefulWidget {
  const FocusSheet({super.key, required this.onStart, required this.loadApps});

  final Future<void> Function(
    List<Site> sites,
    List<String> apps,
    Duration length,
  )
  onStart;
  final Future<List<InstalledApp>> Function() loadApps;

  @override
  State<FocusSheet> createState() => _FocusSheetState();
}

class _FocusSheetState extends State<FocusSheet> {
  final Set<String> _sites = {};
  final List<InstalledApp> _apps = [];
  Duration _length = focusLengths[1];
  bool _starting = false;
  String? _error;

  bool get _anything => _sites.isNotEmpty || _apps.isNotEmpty;

  Future<void> _addApp() async {
    final app = await Navigator.of(context).push<InstalledApp>(
      MaterialPageRoute(
        builder: (_) => PushedPage(
          scroll: false,
          child: AppPicker(apps: widget.loadApps, title: 'ALLOW AN APP'),
        ),
      ),
    );
    if (app == null || !mounted) return;
    setState(() {
      if (!_apps.any((a) => a.packageName == app.packageName)) _apps.add(app);
    });
  }

  Future<void> _start() async {
    setState(() {
      _starting = true;
      _error = null;
    });
    try {
      await widget.onStart(
        sites.where((s) => _sites.contains(s.name)).toList(),
        [for (final a in _apps) a.packageName],
        _length,
      );
      if (mounted) Navigator.of(context).maybePop();
    } catch (e) {
      if (mounted) setState(() => _error = "couldn't start focus: $e");
    } finally {
      if (mounted) setState(() => _starting = false);
    }
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('FOCUS', style: monoStyle(bold: true)),
          const SizedBox(height: 8),
          const Muted(
            'only what you pick can be open. everything else is blocked '
            'until it ends.',
          ),
          const SizedBox(height: 16),
          const Muted('allow sites'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final site in sites)
                SquareChip(
                  site.name,
                  key: Key('focus-site-${site.name}'),
                  selected: _sites.contains(site.name),
                  onTap: () => setState(() {
                    if (!_sites.remove(site.name)) _sites.add(site.name);
                  }),
                ),
            ],
          ),
          const SizedBox(height: 16),
          const Muted('allow apps'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final app in _apps)
                SquareChip(
                  app.label,
                  key: Key('focus-app-${app.packageName}'),
                  selected: true,
                  onTap: () => setState(() => _apps.remove(app)),
                ),
            ],
          ),
          const SizedBox(height: 8),
          AppButton(
            'add an app',
            key: const Key('focus-add-app'),
            onPressed: _addApp,
          ),
          const SizedBox(height: 16),
          const Muted('for'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final length in focusLengths)
                SquareChip(
                  formatDuration(length),
                  key: Key('focus-length-${formatDuration(length)}'),
                  marker: false,
                  exclusive: true,
                  selected: _length == length,
                  onTap: () => setState(() => _length = length),
                ),
            ],
          ),
          const SizedBox(height: 20),
          AppButton(
            _anything
                ? 'focus for ${formatDuration(_length)}'
                : 'pick at least one site or app',
            key: const Key('start-focus'),
            primary: true,
            onPressed: _anything && !_starting ? _start : null,
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(
              _error!,
              key: const Key('focus-error'),
              style: monoStyle(color: AppColors.error),
            ),
          ],
          const SizedBox(height: 8),
          const Muted(
            'calls, the home screen and this app always work. ending focus '
            'early needs the unlock password.',
          ),
          const SizedBox(height: 8),
          AppButton(
            'cancel',
            key: const Key('cancel-focus'),
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
    ),
  );
}
