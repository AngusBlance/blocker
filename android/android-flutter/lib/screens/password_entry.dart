import 'package:flutter/material.dart';

import '../theme.dart';
import '../ui.dart';

/// Shows the long unlock password and asks for it to be typed back by hand
/// (paste is off; the friction is the point). Used for unblocking sites and
/// for changing or ending a running schedule early.
class PasswordEntry extends StatefulWidget {
  const PasswordEntry({
    super.key,
    required this.password,
    required this.title,
    required this.explanation,
    required this.actionLabel,
    required this.onSubmit,
    this.onCancel,
    this.cancelLabel = 'keep it blocked',
  });

  final String password;
  final String title;
  final String explanation;
  final String actionLabel;

  /// Gets what was typed; returns false if it was rejected.
  final Future<bool> Function(String typed) onSubmit;
  final VoidCallback? onCancel;
  final String cancelLabel;

  @override
  State<PasswordEntry> createState() => _PasswordEntryState();
}

class _PasswordEntryState extends State<PasswordEntry> {
  final _input = TextEditingController();
  bool _wrong = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _input.addListener(() => setState(() => _wrong = false));
  }

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() => _busy = true);
    final ok = await widget.onSubmit(_input.text);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _wrong = !ok;
    });
  }

  @override
  Widget build(BuildContext context) {
    final password = widget.password;
    final typed = _input.text.length;
    return Column(
      children: [
        Pane(
          title: widget.title,
          focused: true,
          children: [
            Muted(widget.explanation),
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
              widget.actionLabel,
              key: const Key('unlock-button'),
              primary: true,
              onPressed:
                  password.isNotEmpty && typed == password.length && !_busy
                  ? _submit
                  : null,
            ),
          ],
        ),
        if (widget.onCancel != null) ...[
          const SizedBox(height: 12),
          AppButton(
            widget.cancelLabel,
            key: const Key('password-cancel'),
            onPressed: widget.onCancel,
          ),
        ],
      ],
    );
  }
}

/// Opens a screen asking for the unlock password. Returns what was typed
/// once it matches, or null if cancelled.
Future<String?> askForUnlockPassword(
  BuildContext context, {
  required Future<String> Function() password,
  required String title,
  required String reason,
  required String actionLabel,
}) async {
  final shown = await password();
  if (!context.mounted) return null;
  return Navigator.of(context).push<String>(
    MaterialPageRoute(
      builder: (context) => Scaffold(
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(12),
            child: PasswordEntry(
              password: shown,
              title: title,
              explanation:
                  '$reason type the password below. paste is off on purpose.',
              actionLabel: actionLabel,
              cancelLabel: 'cancel',
              onCancel: () => Navigator.of(context).pop(),
              onSubmit: (typed) async {
                if (typed != shown) return false;
                Navigator.of(context).pop(typed);
                return true;
              },
            ),
          ),
        ),
      ),
    ),
  );
}
