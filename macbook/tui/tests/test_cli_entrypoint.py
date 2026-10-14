import sys

import pytest

from blocker_tui import installer
from blocker_tui.app import main


def test_main_dispatches_to_install_subcommand(monkeypatch):
    calls = []
    monkeypatch.setattr(installer, "install", lambda: calls.append(1))
    monkeypatch.setattr(sys, "argv", ["block", "install"])

    main()

    assert calls == [1]


def test_main_prints_usage_and_exits_zero_for_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["block", "--help"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    assert "usage: block" in capsys.readouterr().out


def test_main_prints_usage_and_exits_nonzero_for_unknown_arg(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["block", "bogus"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "usage: block" in capsys.readouterr().out
