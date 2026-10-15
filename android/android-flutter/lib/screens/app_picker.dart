import 'package:flutter/material.dart';

import '../backend.dart';
import '../theme.dart';
import '../ui.dart';

/// Picks the app a schedule sends you to instead: a searchable list of the
/// phone's apps. Pops with the chosen [InstalledApp].
class AppPicker extends StatefulWidget {
  const AppPicker({super.key, required this.apps});

  final Future<List<InstalledApp>> Function() apps;

  @override
  State<AppPicker> createState() => _AppPickerState();
}

class _AppPickerState extends State<AppPicker> {
  final _search = TextEditingController();
  List<InstalledApp>? _apps;
  String? _error;

  @override
  void initState() {
    super.initState();
    _search.addListener(() => setState(() {}));
    widget.apps().then(
      (apps) {
        if (mounted) setState(() => _apps = apps);
      },
      onError: (Object e) {
        if (mounted) setState(() => _error = "couldn't list apps: $e");
      },
    );
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final query = _search.text.trim().toLowerCase();
    final shown = [
      for (final app in _apps ?? const <InstalledApp>[])
        if (query.isEmpty || app.label.toLowerCase().contains(query)) app,
    ];
    return Pane(
      title: 'Send me to',
      focused: true,
      children: [
        TextField(
          key: const Key('app-search'),
          controller: _search,
          autofocus: true,
          style: monoStyle(),
          decoration: InputDecoration(
            hintText: 'search apps',
            hintStyle: monoStyle(color: AppColors.muted),
            isDense: true,
            contentPadding: const EdgeInsets.all(10),
            enabledBorder: const OutlineInputBorder(
              borderRadius: BorderRadius.zero,
              borderSide: BorderSide(color: AppColors.border),
            ),
            focusedBorder: const OutlineInputBorder(
              borderRadius: BorderRadius.zero,
              borderSide: BorderSide(color: AppColors.accent),
            ),
          ),
        ),
        if (_error != null) Muted(_error!),
        if (_apps == null && _error == null) const Muted('loading apps…'),
        if (_apps != null && shown.isEmpty) const Muted('no apps match.'),
        for (final app in shown)
          InkWell(
            key: Key('app-${app.packageName}'),
            onTap: () => Navigator.of(context).pop(app),
            child: Container(
              constraints: const BoxConstraints(minHeight: 48),
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: AppColors.border)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(app.label, style: monoStyle()),
                  Text(
                    app.packageName,
                    style: monoStyle(color: AppColors.muted, size: 12),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
