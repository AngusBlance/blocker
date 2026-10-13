import pytest

from blocklib.password import (
    check_password,
    get_password,
    is_password_set,
    setup_password,
    unlock_with_password,
)


def test_is_password_set_false_when_missing(tmp_path):
    assert is_password_set(tmp_path / "password.txt") is False


def test_setup_password_creates_file_with_restricted_permissions(tmp_path):
    path = tmp_path / "sub" / "password.txt"
    password = setup_password(path)
    assert path.exists()
    assert get_password(path) == password
    assert oct(path.stat().st_mode)[-3:] == "600"


def test_setup_password_refuses_to_overwrite_existing(tmp_path):
    path = tmp_path / "password.txt"
    setup_password(path)
    with pytest.raises(FileExistsError):
        setup_password(path)


def test_generated_passwords_are_not_trivially_short(tmp_path):
    password = setup_password(tmp_path / "password.txt")
    assert len(password) >= 32


def test_check_password_true_for_correct_value(tmp_path):
    path = tmp_path / "password.txt"
    path.write_text("0000")
    assert check_password("0000", path) is True


def test_check_password_false_for_incorrect_value(tmp_path):
    path = tmp_path / "password.txt"
    path.write_text("0000")
    assert check_password("wrong", path) is False


def test_unlock_with_password_calls_unblock_all_on_match(monkeypatch, tmp_path):
    path = tmp_path / "password.txt"
    path.write_text("0000")
    calls = []
    monkeypatch.setattr(
        "blocklib.password.HostsBlocker.unblock_all",
        lambda self, urls: calls.append((self.hosts_path, urls)),
    )

    result = unlock_with_password("0000", ["netflix.com"], path, tmp_path / "hosts")

    assert result is True
    assert calls == [(tmp_path / "hosts", ["netflix.com"])]


def test_unlock_with_password_does_not_call_unblock_all_on_mismatch(monkeypatch, tmp_path):
    path = tmp_path / "password.txt"
    path.write_text("0000")
    calls = []
    monkeypatch.setattr(
        "blocklib.password.HostsBlocker.unblock_all",
        lambda self, urls: calls.append(1),
    )

    result = unlock_with_password("wrong", ["netflix.com"], path, tmp_path / "hosts")

    assert result is False
    assert calls == []
