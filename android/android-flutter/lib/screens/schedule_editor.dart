import 'package:flutter/material.dart';

import '../schedule.dart';
import '../schedule_format.dart';
import '../sites.dart';
import '../theme.dart';
import '../ui.dart';

/// Picks a time of day; the system clock picker in the app, a stub in tests.
typedef TimePicker = Future<TimeOfDay?> Function(
  BuildContext context,
  TimeOfDay initial,
);

Future<TimeOfDay?> systemTimePicker(BuildContext context, TimeOfDay initial) =>
    showTimePicker(
      context: context,
      initialTime: initial,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
        child: child!,
      ),
    );

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
    this.pickTime = systemTimePicker,
  });

  final Schedule? initial;

  /// Makes an id for a new schedule.
  final String Function() newId;
  final Future<void> Function(Schedule schedule) onSave;
  final Future<void> Function()? onDelete;
  final TimePicker pickTime;

  @override
  State<ScheduleEditor> createState() => _ScheduleEditorState();
}

class _ScheduleEditorState extends State<ScheduleEditor> {
  late final TextEditingController _name;
  late Set<int> _days;
  late int _start;
  late int _end;
  late Set<String> _sites;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final initial = widget.initial;
    final plan = initial?.plan is EveryPlan
        ? initial!.plan as EveryPlan
        : schedulePresets.first.plan;
    _name = TextEditingController(text: initial?.name ?? '');
    _days = {...plan.days};
    _start = plan.start;
    _end = plan.end;
    _sites = {...?initial?.sites};
    _name.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  bool get _allDay => _start == _end;

  bool get _valid =>
      _days.isNotEmpty && _sites.isNotEmpty && _name.text.trim().isNotEmpty;

  void _applyPreset(SchedulePreset preset) => setState(() {
    _days = {...preset.days};
    _start = preset.start;
    _end = preset.end;
    if (_name.text.trim().isEmpty) _name.text = preset.label;
  });

  Future<void> _pick({required bool start}) async {
    final minute = start ? _start : _end;
    final picked = await widget.pickTime(
      context,
      TimeOfDay(hour: minute ~/ 60, minute: minute % 60),
    );
    if (picked == null || !mounted) return;
    setState(() {
      final value = picked.hour * 60 + picked.minute;
      if (start) {
        _start = value;
      } else {
        _end = value;
      }
    });
  }

  Schedule _build() {
    final picked = sites.where((s) => _sites.contains(s.name)).toList();
    final plan = EveryPlan(days: _days, start: _start, end: _end);
    final initial = widget.initial;
    final fields = (
      name: _name.text.trim(),
      sites: [for (final s in picked) s.name],
      domains: [for (final s in picked) ...s.domains],
      apps: [for (final s in picked) ...s.apps],
    );
    if (initial != null) {
      return initial.copyWith(
        name: fields.name,
        sites: fields.sites,
        domains: fields.domains,
        apps: fields.apps,
        plan: plan,
      );
    }
    return Schedule(
      id: widget.newId(),
      name: fields.name,
      sites: fields.sites,
      domains: fields.domains,
      apps: fields.apps,
      plan: plan,
    );
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await widget.onSave(_build());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final plan = _days.isEmpty
        ? null
        : EveryPlan(days: _days, start: _start, end: _end);
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
                    selected:
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
                    onTap: () => _pick(start: true),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _TimeButton(
                    key: const Key('time-to'),
                    label: 'to',
                    minute: _end,
                    enabled: !_allDay,
                    onTap: () => _pick(start: false),
                  ),
                ),
              ],
            ),
            SquareChip(
              'all day',
              key: const Key('all-day'),
              selected: _allDay,
              onTap: () => setState(() {
                if (_allDay) {
                  _start = 9 * 60;
                  _end = 17 * 60;
                } else {
                  _start = 0;
                  _end = 0;
                }
              }),
            ),
            if (plan != null)
              Text(
                formatEvery(plan),
                key: const Key('plan-summary'),
                style: monoStyle(color: AppColors.accent, bold: true),
              ),
            const Muted('sites'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final site in sites)
                  SquareChip(
                    site.name,
                    key: Key('site-chip-${site.name}'),
                    selected: _sites.contains(site.name),
                    onTap: () => setState(() {
                      if (!_sites.remove(site.name)) _sites.add(site.name);
                    }),
                  ),
              ],
            ),
            if (!_valid)
              Muted(
                _days.isEmpty
                    ? 'pick at least one day.'
                    : _sites.isEmpty
                    ? 'pick at least one site.'
                    : 'give it a name.',
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
                onPressed: _saving ? null : widget.onDelete,
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

class _TimeButton extends StatelessWidget {
  const _TimeButton({
    super.key,
    required this.label,
    required this.minute,
    required this.enabled,
    required this.onTap,
  });

  final String label;
  final int minute;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Opacity(
    opacity: enabled ? 1 : 0.35,
    child: Material(
      color: AppColors.surface,
      shape: const RoundedRectangleBorder(
        side: BorderSide(color: AppColors.border),
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
                style: monoStyle(size: 22, bold: true),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
