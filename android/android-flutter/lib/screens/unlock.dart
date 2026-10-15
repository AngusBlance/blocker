import 'package:flutter/material.dart';

import '../blocker.dart';
import '../sites.dart';
import '../theme.dart';
import '../ui.dart';

class UnlockScreen extends StatefulWidget {
  const UnlockScreen({
    super.key,
    required this.blocker,
    required this.site,
    required this.done,
  });

  final Blocker blocker;

  /// The site to unlock, or null to unlock everything that's blocked.
  final Site? site;
  final VoidCallback done;

  @override
  State<UnlockScreen> createState() => _UnlockScreenState();
}

class _UnlockScreenState extends State<UnlockScreen> {
  final _input = TextEditingController();
  String? _password;
  bool _wrong = false;

  @override
  void initState() {
    super.initState();
    widget.blocker.backend.unlockPassword().then(
      (p) => setState(() => _password = p),
    );
    _input.addListener(() => setState(() => _wrong = false));
  }

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  List<Site> get _targets =>
      widget.site != null ? [widget.site!] : widget.blocker.blockedSites;

  Future<void> _submit() async {
    final ok = await widget.blocker.unblock(_input.text, _targets);
    if (!mounted) return;
    if (ok) {
      _input.clear();
      widget.done();
    } else {
      setState(() => _wrong = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_targets.isEmpty) {
      return const Pane(
        title: 'Unlock',
        children: [Muted('nothing is blocked right now.')],
      );
    }
    final password = _password ?? '';
    final typed = _input.text.length;
    return Column(
      children: [
        Pane(
          title: widget.site != null
              ? 'Unlock ${widget.site!.name}'
              : 'Unlock everything',
          focused: true,
          children: [
            const Muted(
              'type the password below to unlock. paste is off on purpose.',
            ),
            Container(
              color: AppColors.surface,
              padding: const EdgeInsets.all(10),
              child: Text(password, style: monoStyle(size: 12)),
            ),
            TextField(
              key: const Key('unlock-input'),
              controller: _input,
              maxLines: null,
              minLines: 3,
              autocorrect: false,
              enableSuggestions: false,
              // No long-press menu, so no paste; typing it is the point.
              enableInteractiveSelection: false,
              style: monoStyle(size: 12),
              decoration: InputDecoration(
                hintText: 'type the password here',
                hintStyle: monoStyle(color: AppColors.muted, size: 12),
                isDense: true,
                contentPadding: const EdgeInsets.all(10),
                enabledBorder: const OutlineInputBorder(
                  borderRadius: BorderRadius.zero,
                  borderSide: BorderSide(color: AppColors.accent),
                ),
                focusedBorder: const OutlineInputBorder(
                  borderRadius: BorderRadius.zero,
                  borderSide: BorderSide(color: AppColors.accent),
                ),
              ),
            ),
            Text(
              _wrong ? "that doesn't match." : '$typed / ${password.length}',
              style: monoStyle(
                size: 12,
                color: _wrong ? AppColors.error : AppColors.muted,
              ),
            ),
            AppButton(
              'unlock',
              key: const Key('unlock-button'),
              primary: true,
              onPressed: password.isNotEmpty && typed == password.length
                  ? _submit
                  : null,
            ),
          ],
        ),
        if (widget.site != null) ...[
          const SizedBox(height: 12),
          AppButton('keep it blocked', onPressed: widget.done),
        ],
      ],
    );
  }
}
