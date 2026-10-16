from blocklib import adult
from blocklib.core import BEGIN_MARK, END_MARK, HostsBlocker
from blocklib.schedule_helper import BEGIN as SCHEDULE_BEGIN
from blocklib.schedule_helper import END as SCHEDULE_END
from blocklib.schedule_helper import render

BASE = "127.0.0.1 localhost\n::1 localhost\n"
MANUAL = f"{BEGIN_MARK}\n127.0.0.1 netflix.com\n::1 netflix.com\n{END_MARK}\n"


def test_shipped_list_is_big_and_holds_the_obvious_sites():
    names = adult.load_names()
    assert len(names) > 50_000
    assert {"pornhub.com", "www.pornhub.com", "xvideos.com"} <= set(names)
    for everyday in ("google.com", "reddit.com", "youtube.com", "wikipedia.org"):
        assert everyday not in names


def test_load_names_skips_comments_and_invalid_names(tmp_path):
    path = tmp_path / "list.txt"
    path.write_text("# header\nPorn.Example\n\nbad_name.com\nlocalhost\n")
    assert adult.load_names(path) == ["porn.example"]


def test_turning_on_blocks_names_and_forces_safesearch():
    on = adult.turned_on(BASE + MANUAL, ["a.example"])
    assert adult.is_on(on)
    assert "127.0.0.1 a.example\n::1 a.example\n" in on
    assert f"{adult.SAFESEARCH_V4} www.google.com" in on
    assert f"{adult.SAFESEARCH_V6} google.com" in on
    assert on.startswith(BASE + MANUAL)


def test_turning_on_twice_keeps_one_section():
    on = adult.turned_on(adult.turned_on(BASE, ["a.example"]), ["b.example"])
    assert on.count(adult.BEGIN) == 1
    assert "a.example" not in on and "b.example" in on


def test_turning_off_leaves_everything_else():
    content = BASE + MANUAL
    assert adult.turned_off(adult.turned_on(content, ["a.example"])) == content
    assert not adult.is_on(content)


def test_section_is_invisible_to_manual_and_scheduled_blocks(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text(adult.turned_on(BASE + MANUAL, ["a.example"]))
    blocker = HostsBlocker(hosts)
    # The extension gets these; the list would overflow Chrome's rule limit.
    assert blocker.all_blocked_urls == {"netflix.com"}
    assert blocker.adult_blocked


def test_manual_and_schedule_writes_keep_the_section():
    on = adult.turned_on(BASE, ["a.example"])
    after_manual = HostsBlocker._remove_domain(
        HostsBlocker._insert_domain(on, "netflix.com"), "netflix.com"
    )
    assert adult.is_on(after_manual) and "::1 a.example" in after_manual
    scheduled = render(on, ["youtube.com"])
    assert SCHEDULE_BEGIN in scheduled and SCHEDULE_END in scheduled
    assert adult.is_on(render(scheduled, []))


def test_block_and_unblock_adult_commit_through_sudo(tmp_path, monkeypatch):
    hosts = tmp_path / "hosts"
    hosts.write_text(BASE)
    written = []
    monkeypatch.setattr(HostsBlocker, "_commit", lambda self, c: written.append(c))
    blocker = HostsBlocker(hosts)
    blocker.block_adult(["a.example"])
    assert adult.is_on(written[-1])
    hosts.write_text(written[-1])
    blocker.unblock_adult()
    assert written[-1] == BASE
