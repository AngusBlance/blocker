import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import '../backend.dart';
import '../schedule.dart';
import '../schedule_format.dart';
import '../sites.dart';
import '../theme.dart';
import '../ui.dart';
import 'app_picker.dart';

/// Creates or edits a recurring schedule: presets for the common cases, then
/// name, days, from–to and sites. [onSave] gets the finished schedule (same
/// id when editing).
class ScheduleEditor extends StatefulWidget {
  const ScheduleEditor({
    super.key,
    this.initial,
    required this.newId,
    required this.onSave,
    this.onDelete,
    this.loadApps,
  });

  final Schedule? initial;

  /// Makes an id for a new schedule.
  final String Function() newId;
  final Future<void> Function(Schedule schedule) onSave;
  final Future<void> Function()? onDelete;

  /// The phone's apps, for "send me to an app". Without it that choice is
  /// hidden.
  final Future<List<InstalledApp>> Function()? loadApps;

  @override
  State<ScheduleEditor> createState() => _ScheduleEditorState();
}

class _ScheduleEditorState extends State<ScheduleEditor> {
  late final TextEditingController _name;
  late final TextEditingController _message;

  /// What happens when something blocked is opened.
  late _ActionKind _action;
  String? _redirectPackage;
  String? _redirectLabel;
  late Set<int> _days;
  late int _start;
  late int _end;
  late Set<String> _sites;
  bool _saving = false;

  /// Which time's wheel is open under the from/to row, if either.
  _TimeEnd? _openTime;

  /// All day is its own switch (rather than "start == end") so picking a
  /// from time equal to the to time can't turn it on by accident, and turning
  /// it off brings back the times from before.
  late bool _allDay;
  late int _timedStart;
  late int _timedEnd;

  @override
  void initState() {
    super.initState();
    final initial = widget.initial;
    final plan = initial?.plan is EveryPlan
        ? initial!.plan as EveryPlan
        : schedulePresets.first.plan;
    _name = TextEditingController(text: initial?.name ?? '');
    _days = {...plan.days};
    _allDay = plan.allDay;
    _timedStart = plan.allDay ? 9 * 60 : plan.start;
    _timedEnd = plan.allDay ? 17 * 60 : plan.end;
    _start = _timedStart;
    _end = _timedEnd;
    _sites = {...?initial?.sites};
    _name.addListener(() => setState(() {}));
    final action = initial?.action ?? const BlockAction();
    _action = switch (action) {
      BlockAction() => _ActionKind.block,
      MessageAction() => _ActionKind.message,
      RedirectAction() => _ActionKind.redirect,
    };
    _message = TextEditingController(
      text: action is MessageAction ? action.text : '',
    );
    _message.addListener(() => setState(() {}));
    if (action is RedirectAction) {
      _redirectPackage = action.packageName;
      // Show the app's name once the list loads; its package until then.
      widget.loadApps?.call().then((apps) {
        if (!mounted) return;
        final match = apps.where((a) => a.packageName == _redirectPackage);
        setState(() {
          _redirectLabel = match.isEmpty
              ? '$_redirectPackage (not installed)'
              : match.first.label;
        });
      }, onError: (_) {});
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _message.dispose();
    super.dispose();
  }

  /// start == end means all day in a schedule, so a timed range can't have
  /// the same from and to.
  bool get _sameTimes => !_allDay && _start == _end;

  ScheduleAction get _scheduleAction => switch (_action) {
    _ActionKind.block => const BlockAction(),
    _ActionKind.message => MessageAction(_message.text.trim()),
    _ActionKind.redirect => RedirectAction(_redirectPackage ?? ''),
  };

  bool get _actionReady => switch (_action) {
    _ActionKind.block => true,
    _ActionKind.message => _message.text.trim().isNotEmpty,
    _ActionKind.redirect => _redirectPackage != null,
  };

  bool get _valid =>
      !_sameTimes &&
      _actionReady &&
      _days.isNotEmpty &&
      _sites.any((name) => sites.any((s) => s.name == name)) &&
      _name.text.trim().isNotEmpty;

  void _applyPreset(SchedulePreset preset) => setState(() {
    _days = {...preset.days};
    _allDay = false;
    _start = _timedStart = preset.start;
    _end = _timedEnd = preset.end;
    // Fill the name in, or swap it if it's still another preset's name.
    final name = _name.text.trim();
    if (name.isEmpty || schedulePresets.any((p) => p.label == name)) {
      _name.text = preset.label;
    }
  });

  void _toggleWheel(_TimeEnd end) =>
      setState(() => _openTime = _openTime == end ? null : end);

  void _setTime(_TimeEnd end, int minute) => setState(() {
    if (end == _TimeEnd.from) {
      _start = _timedStart = minute;
    } else {
      _end = _timedEnd = minute;
    }
  });

  EveryPlan get _plan => _allDay
      ? EveryPlan(days: _days, start: 0, end: 0)
      : EveryPlan(days: _days, start: _start, end: _end);

  /// Site names this app version doesn't know (e.g. removed from the list)
  /// stay as they were, with their domains and apps, rather than vanish.
  List<String> get _unknownSites => [
    for (final name in widget.initial?.sites ?? const <String>[])
      if (!sites.any((s) => s.name == name)) name,
  ];

  Schedule _build() {
    final picked = sites.where((s) => _sites.contains(s.name)).toList();
    final plan = _plan;
    final initial = widget.initial;
    final known = {
      for (final s in sites) ...s.domains,
      for (final s in sites) ...s.apps,
    };
    final keptDomains = [
      for (final d in initial?.domains ?? const <String>[])
        if (_unknownSites.isNotEmpty && !known.contains(d)) d,
    ];
    final keptApps = [
      for (final a in initial?.apps ?? const <String>[])
        if (_unknownSites.isNotEmpty && !known.contains(a)) a,
    ];
    final fields = (
      name: _name.text.trim(),
      sites: [for (final s in picked) s.name, ..._unknownSites],
      domains: [for (final s in picked) ...s.domains, ...keptDomains],
      apps: [for (final s in picked) ...s.apps, ...keptApps],
    );
    if (initial != null) {
      return initial.copyWith(
        name: fields.name,
        sites: fields.sites,
        domains: fields.domains,
        apps: fields.apps,
        plan: plan,
        action: _scheduleAction,
      );
    }
    return Schedule(
      id: widget.newId(),
      name: fields.name,
      sites: fields.sites,
      domains: fields.domains,
      apps: fields.apps,
      plan: plan,
      action: _scheduleAction,
    );
  }

  Future<void> _pickApp() async {
    final load = widget.loadApps;
    if (load == null) return;
    final app = await Navigator.of(context).push<InstalledApp>(
      MaterialPageRoute(
        builder: (_) => PushedPage(scroll: false, child: AppPicker(apps: load)),
      ),
    );
    if (app == null || !mounted) return;
    setState(() {
      _redirectPackage = app.packageName;
      _redirectLabel = app.label;
    });
  }

  /// Runs save or delete with the buttons disabled meanwhile, so a double
  /// tap can't start two.
  Future<void> _busy(Future<void> Function() action) async {
    setState(() => _saving = true);
    try {
      await action();
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _save() => _busy(() => widget.onSave(_build()));

  @override
  Widget build(BuildContext context) {
    final plan = _days.isEmpty || _sameTimes ? null : _plan;
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        Pane(
          title: widget.initial == null ? 'New schedule' : 'Edit schedule',
          focused: true,
          children: [
            const Muted('start from'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final preset in schedulePresets)
                  SquareChip(
                    preset.label,
                    key: Key('preset-${preset.label}'),
                    marker: false,
                    exclusive: true,
                    selected:
                        !_allDay &&
                        _days.length == preset.days.length &&
                        _days.containsAll(preset.days) &&
                        _start == preset.start &&
                        _end == preset.end,
                    onTap: () => _applyPreset(preset),
                  ),
              ],
            ),
            const Muted('name'),
            TextField(
              key: const Key('schedule-name'),
              controller: _name,
              style: monoStyle(),
              decoration: InputDecoration(
                hintText: 'e.g. work',
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
            const Muted('days'),
            Row(
              children: [
                for (var d = 1; d <= 7; d++) ...[
                  if (d > 1) const SizedBox(width: 6),
                  Expanded(
                    child: _DayChip(
                      day: d,
                      selected: _days.contains(d),
                      onTap: () => setState(() {
                        if (!_days.remove(d)) _days.add(d);
                      }),
                    ),
                  ),
                ],
              ],
            ),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (label, days) in [
                  ('weekdays', {1, 2, 3, 4, 5}),
                  ('every day', {1, 2, 3, 4, 5, 6, 7}),
                  ('weekends', {6, 7}),
                ])
                  SquareChip(
                    label,
                    key: Key('days-$label'),
                    marker: false,
                    exclusive: true,
                    selected:
                        _days.length == days.length && _days.containsAll(days),
                    onTap: () => setState(() => _days = {...days}),
                  ),
              ],
            ),
            const Muted('time'),
            Row(
              children: [
                Expanded(
                  child: _TimeButton(
                    key: const Key('time-from'),
                    label: 'from',
                    minute: _start,
                    enabled: !_allDay,
                    open: _openTime == _TimeEnd.from,
                    onTap: () => _toggleWheel(_TimeEnd.from),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _TimeButton(
                    key: const Key('time-to'),
                    label: 'to',
                    minute: _end,
                    enabled: !_allDay,
                    open: _openTime == _TimeEnd.to,
                    onTap: () => _toggleWheel(_TimeEnd.to),
                  ),
                ),
              ],
            ),
            if (_openTime case final end? when !_allDay)
              _TimeWheel(
                // A new wheel for each end, so it starts at that end's time.
                key: ValueKey(end),
                minute: end == _TimeEnd.from ? _start : _end,
                onChanged: (minute) => _setTime(end, minute),
              ),
            SquareChip(
              'all day',
              key: const Key('all-day'),
              selected: _allDay,
              onTap: () => setState(() {
                _allDay = !_allDay;
                _openTime = null;
                _start = _timedStart;
                _end = _timedEnd;
              }),
            ),
            if (plan != null)
              Text(
                formatEvery(plan),
                key: const Key('plan-summary'),
                style: monoStyle(color: AppColors.accent, bold: true),
              ),
            const Muted('sites'),
            // An even grid, two to a row, so the sites line up.
            for (var row = 0; row < sites.length; row += 2)
              Row(
                children: [
                  for (var i = row; i < row + 2; i++) ...[
                    if (i > row) const SizedBox(width: 8),
                    Expanded(
                      child: i < sites.length
                          ? SquareChip(
                              sites[i].name,
                              key: Key('site-chip-${sites[i].name}'),
                              selected: _sites.contains(sites[i].name),
                              onTap: () => setState(() {
                                final name = sites[i].name;
                                if (!_sites.remove(name)) _sites.add(name);
                              }),
                            )
                          : const SizedBox(),
                    ),
                  ],
                ],
              ),
            const Muted('when blocked'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (kind, label) in [
                  (_ActionKind.block, 'block screen'),
                  (_ActionKind.message, 'my message'),
                  if (widget.loadApps != null ||
                      _action == _ActionKind.redirect)
                    (_ActionKind.redirect, 'send me to an app'),
                ])
                  SquareChip(
                    label,
                    key: Key('action-${kind.name}'),
                    marker: false,
                    exclusive: true,
                    selected: _action == kind,
                    onTap: () => setState(() => _action = kind),
                  ),
              ],
            ),
            if (_action == _ActionKind.message)
              TextField(
                key: const Key('action-message-text'),
                controller: _message,
                style: monoStyle(),
                maxLength: 120,
                decoration: InputDecoration(
                  hintText: 'e.g. go to bed',
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
            if (_action == _ActionKind.redirect)
              AppButton(
                _redirectPackage == null
                    ? 'pick an app'
                    : 'send me to ${_redirectLabel ?? _redirectPackage}',
                key: const Key('pick-app'),
                onPressed: widget.loadApps == null ? null : _pickApp,
              ),
            if (!_valid)
              Muted(
                _sameTimes
                    ? "from and to can't be the same time."
                    : _days.isEmpty
                    ? 'pick at least one day.'
                    : !_sites.any((name) => sites.any((s) => s.name == name))
                    ? 'pick at least one site.'
                    : _name.text.trim().isEmpty
                    ? 'give it a name.'
                    : _action == _ActionKind.message
                    ? 'write your message.'
                    : 'pick an app to send you to.',
              ),
            AppButton(
              'save',
              key: const Key('save-schedule'),
              primary: true,
              onPressed: _valid && !_saving ? _save : null,
            ),
            if (widget.onDelete != null)
              AppButton(
                'delete',
                key: const Key('delete-schedule'),
                onPressed: _saving ? null : () => _busy(widget.onDelete!),
              ),
          ],
        ),
      ],
    );
  }
}

class _DayChip extends StatelessWidget {
  const _DayChip({
    required this.day,
    required this.selected,
    required this.onTap,
  });

  static const _letters = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
  static const _names = [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
  ];

  final int day;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
    label: _names[day - 1],
    selected: selected,
    button: true,
    onTap: onTap,
    excludeSemantics: true,
    child: AspectRatio(
      aspectRatio: 1,
      child: Material(
        key: Key('day-$day'),
        color: selected ? AppColors.accent : AppColors.background,
        shape: RoundedRectangleBorder(
          side: BorderSide(
            color: selected ? AppColors.accent : AppColors.border,
          ),
        ),
        child: InkWell(
          onTap: onTap,
          child: Center(
            child: Text(
              _letters[day - 1],
              style: monoStyle(
                bold: true,
                color: selected ? AppColors.background : AppColors.muted,
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

enum _TimeEnd { from, to }

/// A scroll wheel for a time of day (Flutter's own Cupertino picker), 24
/// hour, in 5-minute steps, or 1-minute ones if the time isn't on a 5.
class _TimeWheel extends StatelessWidget {
  const _TimeWheel({super.key, required this.minute, required this.onChanged});

  final int minute;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) => Container(
    height: 180,
    decoration: BoxDecoration(
      color: AppColors.surface,
      border: Border.all(color: AppColors.accent),
    ),
    child: CupertinoTheme(
      data: CupertinoThemeData(
        brightness: Brightness.dark,
        textTheme: CupertinoTextThemeData(
          dateTimePickerTextStyle: monoStyle(size: 22),
        ),
      ),
      child: CupertinoDatePicker(
        key: const Key('time-wheel'),
        mode: CupertinoDatePickerMode.time,
        use24hFormat: true,
        minuteInterval: minute % 5 == 0 ? 5 : 1,
        initialDateTime: DateTime(2000, 1, 1, minute ~/ 60, minute % 60),
        onDateTimeChanged: (t) => onChanged(t.hour * 60 + t.minute),
      ),
    ),
  );
}

class _TimeButton extends StatelessWidget {
  const _TimeButton({
    super.key,
    required this.label,
    required this.minute,
    required this.enabled,
    required this.open,
    required this.onTap,
  });

  final String label;
  final int minute;
  final bool enabled;

  /// Its wheel is showing.
  final bool open;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Opacity(
    opacity: enabled ? 1 : 0.35,
    child: Material(
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: open ? AppColors.accent : AppColors.border),
      ),
      child: InkWell(
        onTap: enabled ? onTap : null,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Column(
            children: [
              Text(label, style: monoStyle(color: AppColors.muted, size: 12)),
              Text(
                formatMinute(minute),
                style: monoStyle(
                  size: 22,
                  bold: true,
                  color: open ? AppColors.accent : AppColors.foreground,
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

enum _ActionKind { block, message, redirect }
