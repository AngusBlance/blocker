import 'package:flutter/material.dart';

import '../sites.dart';
import '../theme.dart';
import '../ui.dart';

/// How long "block now" lasts: a fixed length, or until the next 7am.
class BlockLength {
  const BlockLength.of(this.duration) : untilMorning = false;
  const BlockLength.untilMorning() : duration = null, untilMorning = true;

  final Duration? duration;
  final bool untilMorning;

  /// The next 07:00 at least half an hour away, so "until 7am" just before
  /// 7 means tomorrow rather than a few minutes.
  static DateTime nextMorning(DateTime now) {
    final today = DateTime(now.year, now.month, now.day, 7);
    return now.add(const Duration(minutes: 30)).isBefore(today)
        ? today
        : DateTime(now.year, now.month, now.day + 1, 7);
  }

  DateTime endFrom(DateTime now) =>
      untilMorning ? nextMorning(now) : now.add(duration!);

  String get label => untilMorning ? 'until 7am' : formatDuration(duration!);
}

const presetLengths = [
  BlockLength.of(Duration(minutes: 15)),
  BlockLength.of(Duration(minutes: 30)),
  BlockLength.of(Duration(hours: 1)),
  BlockLength.of(Duration(hours: 2)),
  BlockLength.untilMorning(),
];

const _step = Duration(minutes: 15);
const _minCustom = Duration(minutes: 15);
const _maxCustom = Duration(hours: 12);

/// "Block now for…": pick sites (all picked to start with, since that's what
/// "block now" usually means), pick how long, start. Three taps. Calls
/// [onStart] with the chosen sites, the moment it starts and when it ends
/// (both from one reading of the clock).
class BlockNowSheet extends StatefulWidget {
  const BlockNowSheet({super.key, required this.now, required this.onStart});

  final DateTime Function() now;
  final Future<void> Function(
    List<Site> sites,
    DateTime startsAt,
    DateTime endsAt,
  )
  onStart;

  @override
  State<BlockNowSheet> createState() => _BlockNowSheetState();
}

class _BlockNowSheetState extends State<BlockNowSheet> {
  final Set<String> _picked = {for (final s in sites) s.name};
  BlockLength _length = presetLengths[2]; // 1h
  bool _custom = false;
  Duration _customLength = const Duration(minutes: 45);
  bool _starting = false;

  BlockLength get _chosen => _custom ? BlockLength.of(_customLength) : _length;

  String get _startLabel {
    final n = _picked.length;
    final what = n == 1 ? '1 site' : '$n sites';
    return _chosen.untilMorning
        ? 'block $what until 7am'
        : 'block $what for ${_chosen.label}';
  }

  String? _error;

  Future<void> _start() async {
    setState(() {
      _starting = true;
      _error = null;
    });
    final picked = sites.where((s) => _picked.contains(s.name)).toList();
    final startsAt = widget.now();
    try {
      await widget.onStart(picked, startsAt, _chosen.endFrom(startsAt));
      if (mounted) Navigator.of(context).maybePop();
    } catch (e) {
      if (mounted) setState(() => _error = "couldn't start the block: $e");
    } finally {
      if (mounted) setState(() => _starting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('BLOCK NOW', style: monoStyle(bold: true)),
            const SizedBox(height: 16),
            const Muted('sites'),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final site in sites)
                  SquareChip(
                    site.name,
                    key: Key('pick-${site.name}'),
                    selected: _picked.contains(site.name),
                    onTap: () => setState(() {
                      if (!_picked.remove(site.name)) _picked.add(site.name);
                    }),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            const Muted('for'),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final length in presetLengths)
                  SquareChip(
                    length.label,
                    key: Key('length-${length.label}'),
                    marker: false,
                    selected: !_custom && _length.label == length.label,
                    onTap: () => setState(() {
                      _custom = false;
                      _length = length;
                    }),
                  ),
                SquareChip(
                  'custom',
                  key: const Key('length-custom'),
                  marker: false,
                  selected: _custom,
                  onTap: () => setState(() => _custom = true),
                ),
              ],
            ),
            if (_custom) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  _StepButton(
                    '−',
                    semantics: 'shorter',
                    key: const Key('custom-less'),
                    onTap: _customLength > _minCustom
                        ? () => setState(() => _customLength -= _step)
                        : null,
                  ),
                  Expanded(
                    child: Center(
                      child: Text(
                        formatDuration(_customLength),
                        key: const Key('custom-length'),
                        style: monoStyle(size: 18, bold: true),
                      ),
                    ),
                  ),
                  _StepButton(
                    '+',
                    semantics: 'longer',
                    key: const Key('custom-more'),
                    onTap: _customLength < _maxCustom
                        ? () => setState(() => _customLength += _step)
                        : null,
                  ),
                ],
              ),
            ],
            const SizedBox(height: 20),
            AppButton(
              _startLabel,
              key: const Key('start-block'),
              primary: true,
              onPressed: _picked.isEmpty || _starting ? null : _start,
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(
                _error!,
                key: const Key('block-error'),
                style: monoStyle(color: AppColors.error),
              ),
            ],
            const SizedBox(height: 8),
            const Muted('ending it early needs the unlock password.'),
            const SizedBox(height: 8),
            AppButton(
              'cancel',
              key: const Key('cancel-block'),
              onPressed: () => Navigator.of(context).maybePop(),
            ),
          ],
        ),
      ),
    );
  }
}

class _StepButton extends StatelessWidget {
  const _StepButton(
    this.label, {
    super.key,
    required this.semantics,
    required this.onTap,
  });

  final String label;
  final String semantics;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Semantics(
    label: semantics,
    button: true,
    excludeSemantics: true,
    child: SizedBox(
      width: 56,
      height: 48,
      child: Opacity(
        opacity: onTap == null ? 0.35 : 1,
        child: Material(
          color: AppColors.surface,
          shape: const RoundedRectangleBorder(
            side: BorderSide(color: AppColors.border),
          ),
          child: InkWell(
            onTap: onTap,
            child: Center(
              child: Text(label, style: monoStyle(size: 20, bold: true)),
            ),
          ),
        ),
      ),
    ),
  );
}
