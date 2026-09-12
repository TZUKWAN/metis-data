"""Phase I acceptance: uniform EntityResolver protocol, generic exact-match resolver, factory."""
from __future__ import annotations

from app.builds.entities import (
    ChinaRegionResolver,
    CountryResolver,
    EntityMatch,
    EntityResolver,
    GenericStringEntityResolver,
    get_resolver,
)


def test_generic_exact_match_identity():
    """strip+casefold equality is the same entity; anything else never collapses."""
    r = GenericStringEntityResolver()
    a = r.normalize("Microsoft Corp")
    b = r.normalize("  microsoft CORP ")
    assert isinstance(a, EntityMatch) and isinstance(b, EntityMatch)
    assert r.canonical_key(a) == r.canonical_key(b)
    assert a.kind == "generic" and a.method == "exact_name" and a.confidence == 1.0
    # no fuzzy ever: a typo is a DIFFERENT entity, not a silent correction
    assert r.canonical_key(r.normalize("Microsoft")) != r.canonical_key(r.normalize("Microsft"))
    # different strings → different canonical keys
    assert r.canonical_key(r.normalize("Apple")) != r.canonical_key(r.normalize("Microsoft Corp"))
    # empty / None → unresolved (never guessed)
    assert r.normalize("") is None
    assert r.normalize("   ") is None
    assert r.normalize(None) is None


def test_generic_detect():
    r = GenericStringEntityResolver()
    assert r.detect("firm_name", ["ACME", " Globex "]) is True
    assert r.detect("anything", [None, "", "  "]) is False
    assert r.detect("x", []) is False


def test_protocol_conformance():
    """All resolvers satisfy the EntityResolver protocol (detect/normalize/canonical_key)."""
    for impl in (CountryResolver(), ChinaRegionResolver(), ChinaRegionResolver(level="province"), GenericStringEntityResolver()):
        assert isinstance(impl, EntityResolver)


def test_country_resolver_protocol_methods():
    r = CountryResolver()
    m1 = r.normalize("United States")
    m2 = r.normalize("USA")
    assert m1 and m2
    assert r.canonical_key(m1) == r.canonical_key(m2) == "USA"  # canonical key is ISO3
    assert r.normalize("Atlantis") is None  # unknown stays unresolved
    assert r.detect("country_name", ["United States", "China"]) is True  # name hint
    assert r.detect("country", []) is True
    assert r.detect("gdp", [1.0, 2.0]) is False  # numeric column, nothing resolves


def test_china_resolver_protocol_methods():
    rp = ChinaRegionResolver(level="province")
    m = rp.normalize("北京")
    assert m and rp.canonical_key(m) == "110000"
    assert rp.normalize("北京", year=1950) is None  # not valid before 1955 — no silent mapping
    rc = ChinaRegionResolver()  # default level: prefecture
    w = rc.normalize("武汉", year=2020)
    assert w and rc.canonical_key(w) == "420100"
    assert rc.detect("城市", ["武汉", "成都"]) is True
    assert rc.detect("unemployment", [9.7, 7.0]) is False


def test_get_resolver_factory():
    # country → CountryResolver (ISO3 keys)
    country = get_resolver("country")
    assert isinstance(country, CountryResolver)
    assert country.canonical_key(country.normalize("China")) == "CHN"
    # province / city / prefecture → ChinaRegionResolver with the right level
    province = get_resolver("province")
    assert isinstance(province, ChinaRegionResolver) and province.level == "province"
    city = get_resolver("city")
    assert isinstance(city, ChinaRegionResolver) and city.level == "prefecture"
    assert city.canonical_key(city.normalize("武汉")) == "420100"
    assert get_resolver("prefecture").level == "prefecture"
    # non-geographic units → generic exact-match resolver
    for unit in ("firm", "university", "individual", "entity", "whatever"):
        assert isinstance(get_resolver(unit), GenericStringEntityResolver)
