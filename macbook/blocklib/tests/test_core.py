from blocklib.core import BEGIN_MARK, END_MARK, HostsBlocker

BASE_HOSTS = "127.0.0.1 localhost\n::1 localhost\n"

WITH_BLOCK = (
    BASE_HOSTS
    + f"{BEGIN_MARK}\n"
    + "127.0.0.1 netflix.com\n"
    + "::1 netflix.com\n"
    + "127.0.0.1 youtube.com\n"
    + "::1 youtube.com\n"
    + f"{END_MARK}\n"
)


def write_hosts(tmp_path, content):
    path = tmp_path / "hosts"
    path.write_text(content)
    return path


def test_blocked_urls_empty_when_no_block(tmp_path):
    blocker = HostsBlocker(write_hosts(tmp_path, BASE_HOSTS))
    assert blocker.blocked_urls == set()
    assert blocker.is_active is False
    assert len(blocker) == 0


def test_blocked_urls_returns_domains_in_block(tmp_path):
    blocker = HostsBlocker(write_hosts(tmp_path, WITH_BLOCK))
    assert blocker.blocked_urls == {"netflix.com", "youtube.com"}
    assert blocker.is_active is True
    assert len(blocker) == 2


def test_contains_and_is_blocked_agree(tmp_path):
    blocker = HostsBlocker(write_hosts(tmp_path, WITH_BLOCK))
    assert blocker.is_blocked("netflix.com") is True
    assert "netflix.com" in blocker
    assert blocker.is_blocked("crunchyroll.com") is False
    assert "crunchyroll.com" not in blocker


def test_insert_creates_new_block_when_none_exists():
    result = HostsBlocker._insert_domain(BASE_HOSTS, "netflix.com")
    assert BEGIN_MARK in result
    assert END_MARK in result
    assert "127.0.0.1 netflix.com" in result
    assert "::1 netflix.com" in result
    assert HostsBlocker._parse_blocked_urls(result) == {"netflix.com"}


def test_insert_preserves_content_outside_block():
    result = HostsBlocker._insert_domain(BASE_HOSTS, "netflix.com")
    assert "127.0.0.1 localhost" in result
    assert "::1 localhost" in result


def test_insert_adds_to_existing_block_without_disturbing_others():
    result = HostsBlocker._insert_domain(WITH_BLOCK, "crunchyroll.com")
    assert HostsBlocker._parse_blocked_urls(result) == {
        "netflix.com",
        "youtube.com",
        "crunchyroll.com",
    }


def test_insert_is_idempotent_when_already_blocked():
    result = HostsBlocker._insert_domain(WITH_BLOCK, "netflix.com")
    assert result == WITH_BLOCK


def test_remove_deletes_only_target_domain():
    result = HostsBlocker._remove_domain(WITH_BLOCK, "netflix.com")
    assert HostsBlocker._parse_blocked_urls(result) == {"youtube.com"}
    assert BEGIN_MARK in result
    assert END_MARK in result


def test_remove_drops_whole_block_when_last_domain_removed():
    only_netflix = HostsBlocker._insert_domain(BASE_HOSTS, "netflix.com")
    result = HostsBlocker._remove_domain(only_netflix, "netflix.com")
    assert BEGIN_MARK not in result
    assert END_MARK not in result
    assert HostsBlocker._parse_blocked_urls(result) == set()


def test_remove_preserves_content_outside_block():
    result = HostsBlocker._remove_domain(WITH_BLOCK, "netflix.com")
    assert "127.0.0.1 localhost" in result
    assert "::1 localhost" in result


def test_remove_is_noop_when_url_not_present():
    result = HostsBlocker._remove_domain(WITH_BLOCK, "crunchyroll.com")
    assert result == WITH_BLOCK


def test_remove_is_noop_when_no_block_exists():
    assert HostsBlocker._remove_domain(BASE_HOSTS, "netflix.com") == BASE_HOSTS


def test_round_trip_insert_then_remove_all():
    content = BASE_HOSTS
    for url in ["netflix.com", "youtube.com", "crunchyroll.com"]:
        content = HostsBlocker._insert_domain(content, url)
    assert HostsBlocker._parse_blocked_urls(content) == {
        "netflix.com",
        "youtube.com",
        "crunchyroll.com",
    }

    for url in ["netflix.com", "youtube.com", "crunchyroll.com"]:
        content = HostsBlocker._remove_domain(content, url)
    assert HostsBlocker._parse_blocked_urls(content) == set()
    assert BEGIN_MARK not in content
    assert "127.0.0.1 localhost" in content


def test_str_reports_state_and_count(tmp_path):
    blocker = HostsBlocker(write_hosts(tmp_path, WITH_BLOCK))
    text = str(blocker)
    assert "active" in text
    assert "2" in text


def test_str_reports_inactive_when_empty(tmp_path):
    blocker = HostsBlocker(write_hosts(tmp_path, BASE_HOSTS))
    assert "inactive" in str(blocker)


def test_repr_includes_hosts_path(tmp_path):
    path = write_hosts(tmp_path, BASE_HOSTS)
    assert str(path) in repr(HostsBlocker(path))


def test_privileged_writes_take_the_schedule_helpers_lock(tmp_path, monkeypatch):
    from blocklib import core
    from blocklib.schedule_helper import LOCK_FILE

    calls = []
    monkeypatch.setattr(core.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    HostsBlocker(write_hosts(tmp_path, BASE_HOSTS)).block("netflix.com")
    cp = calls[0]
    assert cp[:3] == ["sudo", "/usr/bin/lockf", "-k"]
    assert str(LOCK_FILE) in cp and cp[-3] == "cp"
