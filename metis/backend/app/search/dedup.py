"""Deduplication (P10-008/009, A4).

- exact: same normalized DOI OR same canonical URL → one logical candidate;
  every mirror is preserved as an acquisition source (provenance kept);
- fuzzy: title+year similarity — only auto-merge at high confidence; low
  confidence results are flagged for review, never auto-merged (A4).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.domain.schemas import new_id


def _canon_url(u: str) -> str:
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#")[0].split("?")[0]
    return u.rstrip("/")


def _norm_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    return d.lower() if d.lower().startswith("10.") else None


def _title_key(title: str) -> str:
    t = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def title_similarity(a: str, b: str) -> float:
    ka, kb = _title_key(a), _title_key(b)
    if not ka or not kb:
        return 0.0
    return SequenceMatcher(None, ka, kb).ratio()


def deduplicate(candidates: list[dict]) -> list[list[dict]]:
    """Group candidates; mark primary + mirrors. Returns groups (each: primary first)."""
    by_doi: dict[str, list[dict]] = {}
    by_url: dict[str, list[dict]] = {}
    singles: list[dict] = []

    def _register(index: dict, key: str, c: dict) -> None:
        index.setdefault(key, []).append(c)

    for c in candidates:
        d = _norm_doi(c.get("doi"))
        if d:
            _register(by_doi, d, c)
            continue
        url = _canon_url(c.get("sources") and c["sources"][0].get("source_url") or "")
        if url:
            _register(by_url, url, c)
        else:
            singles.append(c)

    groups: list[list[dict]] = []

    def _merge_group(members: list[dict]) -> None:
        if not members:
            return
        members = sorted(members, key=lambda c: -(c.get("score") or 0))
        primary = members[0]
        gid = primary.get("dedup_group_id") or f"dg_{new_id('x')[-12:]}"
        seen_provider_urls = set()
        all_sources: list[dict] = []
        for m in members:
            m["dedup_group_id"] = gid
            m["is_primary"] = m is primary
            for s in m.get("sources", []) or []:
                k = _canon_url(s.get("source_url", ""))
                if k not in seen_provider_urls:
                    seen_provider_urls.add(k)
                    all_sources.append(s)
        if len(members) > 1:
            primary["sources"] = all_sources
            primary.setdefault("reasons", []).append(f"merged {len(members)} identical records across providers; mirrors preserved as acquisition sources")
        groups.append(members)

    for members in by_doi.values():
        _merge_group(members)
    claimed = {id(c) for g in groups for c in g}
    for members in by_url.values():
        members = [m for m in members if id(m) not in claimed]
        if members:
            _merge_group(members)
            claimed.update(id(c) for c in members)
    singles += [c for c in candidates if id(c) not in claimed and not c.get("dedup_group_id")]
    for c in singles:
        if id(c) not in claimed:
            c["is_primary"] = True
            groups.append([c])
            claimed.add(id(c))
    return groups


def fuzzy_merge_review(groups: list[list[dict]], threshold: float = 0.92) -> list[dict]:
    """Low-confidence (below threshold) title matches are NEVER auto-merged (A4).

    Returns review flags: pairs that look similar but stay separate + reason.
    Version/year differences must not be merged just because titles look alike.
    """
    flags: list[dict] = []
    flat = [g[0] for g in groups if g]
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            a, b = flat[i], flat[j]
            sim = title_similarity(a.get("title", ""), b.get("title", ""))
            if 0.80 <= sim < 1.0:
                same_version = (a.get("version") or "") == (b.get("version") or "")
                same_year = (a.get("time_coverage") or {}).get("start") == (b.get("time_coverage") or {}).get("start")
                auto = sim >= threshold and same_version and same_year and (a.get("provider_id") != b.get("provider_id"))
                if not auto:
                    flags.append(
                        {
                            "a": a.get("candidate_id"),
                            "b": b.get("candidate_id"),
                            "similarity": round(sim, 3),
                            "auto_merged": False,
                            "reason": "similar title but different version/year/provider — kept separate pending user review",
                        }
                    )
    return flags
