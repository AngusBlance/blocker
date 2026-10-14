from blocklib.domain import Domain, known_domains


def test_domain_defaults_to_not_blocked():
    d = Domain(url="example.com", name="Example")
    assert d.is_blocked is False


def test_domain_fields():
    d = Domain(url="example.com", name="Example", is_blocked=True)
    assert d.url == "example.com"
    assert d.name == "Example"
    assert d.is_blocked is True


def test_known_domains_contains_expected_entries():
    domains = known_domains()
    urls = {d.url for d in domains}
    assert "netflix.com" in urls
    assert "www.netflix.com" in urls
    assert "youtube.com" in urls
    assert "googlevideo.com" in urls
    assert "crunchyroll.com" in urls


def test_known_domains_all_default_unblocked():
    domains = known_domains()
    assert all(d.is_blocked is False for d in domains)


def test_known_domains_returns_independent_copies():
    first = known_domains()
    first[0].is_blocked = True
    second = known_domains()
    assert second[0].is_blocked is False
