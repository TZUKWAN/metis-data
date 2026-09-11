"""Provider selection (P10-003) and query planning (P10-004).

Selection respects research context: official/international sources rank above
community platforms for macro demands; excluded_sources always drop out.
Query plan = per-provider localized/expanded keyword strategies (recomputed when
the requirement changes, A1).
"""
from __future__ import annotations

from app.domain.schemas import DataRequirement, ProviderRecord
from app.providers.registry import get_registry

TRUST_RANK = {"international": 5, "official": 4, "academic": 3, "nonprofit": 3, "community": 2, "commercial": 1}

MACRO_TOPICS = ["gdp", "unemployment", "inflation", "trade", "population", "education", "labor", "health", "就业", "经济", "教育", "失业", "人口"]
CHINA_INDICATORS = ["中国", "china", "province", "省级", "地级"]

CATEGORY_BY_CONTEXT = {
    "macro": ["international_org", "us_gov", "europe", "other_gov", "cn_gov", "research_repo", "ai_community", "catalog", "cn_science", "cloud_marketplace"],
}


def _is_macro_demand(req: DataRequirement) -> bool:
    text = (req.raw_request or "").lower() + " " + " ".join(req.variables.all_named())
    return any(t in text for t in MACRO_TOPICS)


def select_providers(req: DataRequirement, max_providers: int = 8, candidate_pool: int | None = None) -> list[ProviderRecord]:
    """Rank providers by research-context fit. Hard constraints first (A5):
    excluded_sources are removed no matter what; preferred/trust requirements
    dominate ranking; community platforms never outrank official sources for
    macro demands."""
    reg = get_registry()
    excluded = set(req.excluded_sources or [])
    text = (req.raw_request or "").lower()
    vars_text = " ".join(req.variables.all_named()).lower()
    china_context = any(k in text for k in CHINA_INDICATORS) or "CN" in (req.geography or [])
    macro = _is_macro_demand(req)

    scored: list[tuple[float, ProviderRecord]] = []
    for p in reg.all():
        if p.provider_id in excluded or p.status != "active":
            continue
        score = 0.0
        score += TRUST_RANK.get(p.trust_class, 1) * 2.0
        if macro and p.category == "international_org":
            score += 6.0
        if macro and p.category in ("us_gov", "europe", "other_gov", "cn_gov"):
            score += 3.0
        if china_context and (p.category in ("cn_gov", "cn_science") or "CN" in p.country_or_region):
            score += 5.0
        # topic hits in provider name (rough topic affinity)
        name = (p.name or "").lower()
        if "labour" in name or "labor" in name or "ilo" in name:
            if "unemploy" in text or "失业" in text or "labor" in vars_text:
                score += 4.0
        if "unesco" in name and ("education" in text or "教育" in text):
            score += 4.0
        if "education" in name and ("education" in text or "教育" in text):
            score += 3.0
        # user explicit preference boosts (but excluded still wins)
        for pref in req.preferred_sources or []:
            if pref in (p.provider_id, p.category, p.trust_class) or (pref == "official" and p.trust_class == "official") or (pref == "international_org" and p.category == "international_org"):
                score += 8.0
        # access tolerance
        if req.access_tolerance == "public_only":
            caps = p.capabilities.model_dump()
            if not caps.get("anonymous_download") and not caps.get("discovery_api"):
                score -= 3.0
        # only providers with real search capability are usable now
        caps = p.capabilities.model_dump()
        if not (caps.get("discovery_api") or caps.get("discovery_http") or caps.get("discovery_browser")):
            score -= 100.0  # still registered, but not searchable yet
        # community platforms never beat official for macro demands (soft guard)
        if macro and p.trust_class == "commercial":
            score -= 1.5
        scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    if candidate_pool:
        return [p for _, p in scored[:candidate_pool]]
    return [p for s, p in scored[:max_providers] if s > -50]


def plan_queries(req: DataRequirement, providers: list[ProviderRecord]) -> dict[str, list[str]]:
    """P10-004: provider-specific query strategy (multi-language, indicator split)."""
    base_terms: list[str] = []
    text = req.raw_request
    vars_ = req.variables.all_named()
    if vars_:
        base_terms = vars_
    else:
        base_terms = [w for w in text.split() if len(w) >= 3][:6]

    translations = {
        "youth_unemployment_rate": ["youth unemployment rate", "青年失业率", "taux de chômage des jeunes"],
        "unemployment_rate": ["unemployment rate", "失业率"],
        "gdp_per_capita": ["GDP per capita", "人均GDP", "人均国内生产总值"],
        "gdp": ["GDP", "国内生产总值"],
        "education_level": ["education level", "教育水平", "educational attainment"],
        "population": ["population", "人口"],
    }
    plan: dict[str, list[str]] = {}
    for p in providers:
        queries: list[str] = []
        for v in vars_:
            for variant in translations.get(v, [v]):
                queries.append(variant)
        if not queries:
            queries = [" ".join(base_terms[:4])]
        # English-language platforms get English; Chinese platforms get Chinese variants too
        if p.category in ("cn_gov", "cn_science"):
            queries = [q for q in queries] + [t for v in vars_ for t in translations.get(v, []) if any("\u4e00" <= c <= "\u9fff" for c in t)]
            queries = queries or [text[:40]]
        if p.provider_id == "un_comtrade" and req.time_range:
            queries = [f"trade {req.time_range[1]}"]
        # dedupe preserving order, cap 4
        seen: set[str] = set()
        queries = [q for q in queries if not (q in seen or seen.add(q))][:4]
        plan[p.provider_id] = queries
    return plan
