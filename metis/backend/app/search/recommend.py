"""Candidate recommendation (P10-010..015, A5).

Multi-dimension scoring with explicit reasons/limitations/unknowns. Unknowns are
never treated as satisfied; license UNKNOWN never counts as open; variable hints
are only credited when a provider metadata match is plausible — title keyword
hits alone never claim a variable exists.
"""
from __future__ import annotations

import re

from app.providers.registry import get_registry

TRUST = {"international": 1.0, "official": 0.9, "academic": 0.7, "nonprofit": 0.6, "community": 0.4, "commercial": 0.3}
OPEN_LICENSES = re.compile(r"cc0|cc-?by(?!-nc|-nd)|pddl|odc-by|public domain|usgov|ogl|etalab|open", re.I)


def _vars_from_requirement(requirement: dict) -> list[str]:
    v = requirement.get("variables") or {}
    # PlanningBundle format: list of {concept, role}
    if isinstance(v, list):
        return [item.get("concept", "") for item in v if isinstance(item, dict) and item.get("concept")]
    # legacy dict format: {role: [name,...]}
    out = []
    for role in ("outcomes", "exposures", "mediators", "moderators", "controls", "identifiers", "optional"):
        out += v.get(role) or []
    return out


def _variable_coverage(candidate: dict, required_vars: list[str]) -> tuple[float, list[str], list[str]]:
    """Returns (coverage 0..1, matched, unknown-required).

    Matching requires a plausible hint in variable_hints OR indicator-style
    source_ref; a title keyword hit alone is NOT enough (A5).
    """
    if not required_vars:
        return 0.5, [], [v for v in required_vars]
    hints = " ".join(candidate.get("variable_hints") or []).lower()
    ref = (candidate.get("source_ref") or "").lower()
    desc = (candidate.get("description") or "").lower()
    matched, unknown = [], []
    for v in required_vars:
        parts = v.split("_")
        hint_hit = any(p in hints for p in ([v] + parts if len(parts) > 1 else [v]) if len(p) >= 4)
        ref_hit = any(p in ref for p in ([v] + parts if len(parts) > 1 else [v]) if len(p) >= 4)
        desc_hit = any(p in desc for p in parts if len(p) >= 5)
        if hint_hit or ref_hit:
            matched.append(v)
        elif desc_hit:
            matched.append(v)  # weaker evidence, still more than title-only
        else:
            unknown.append(v)
    return (len(matched) / len(required_vars)), matched, unknown


def evaluate_candidates(candidates: list[dict], requirement: dict) -> list[dict]:
    """Sets score breakdown + reasons/limitations/unknowns on each candidate."""
    required_vars = _vars_from_requirement(requirement)
    req_geo = set(requirement.get("geography") or [])
    req_time = requirement.get("time_range")
    trust_req = (requirement.get("trust_requirement") or "").lower()

    for c in candidates:
        reg_rec = None
        try:
            reg_rec = get_registry().get(c.get("provider_id", ""))
        except Exception:  # noqa: BLE001
            pass
        reasons: list[str] = []
        limitations: list[str] = []
        unknowns: list[str] = []
        br = c.setdefault("recommendation", {})

        # topic
        title = (c.get("title") or "").lower()
        topic_hits = sum(1 for v in required_vars if any(p in title for p in v.split("_") if len(p) >= 4))
        br["topic"] = min(1.0, 0.3 * topic_hits)
        # variables — honest coverage
        cov, matched, unknown_vars = _variable_coverage(c, required_vars)
        br["variables"] = cov
        if matched:
            reasons.append("variable coverage: " + ", ".join(matched))
        if unknown_vars:
            unknowns.append("no evidence these required variables exist in this dataset: " + ", ".join(unknown_vars))
        # hard constraint: missing core variables must not be masked by official source (A5)
        if required_vars and cov == 0:
            br["variables"] = 0.0
            limitations.append("no required variable evidence — official source status does not compensate")

        # unit
        unit = (c.get("unit_of_analysis") or "UNKNOWN").lower()
        req_unit = (requirement.get("unit_of_analysis") or "").lower()
        br["unit"] = 1.0 if unit == req_unit and unit else (0.4 if unit in ("country", req_unit) else 0.2)
        if unit == "unknown":
            unknowns.append("unit of analysis unknown")

        # time
        tc = c.get("time_coverage") or {}
        t_start, t_end = tc.get("start"), tc.get("end")
        if isinstance(req_time, dict):  # PlanningBundle shape {"start":..,"end":..}
            req_time = [req_time.get("start"), req_time.get("end")]
            requirement["time_range"] = req_time
        if req_time and t_start and t_end:
            try:
                s, e = int(str(t_start)[:4]), int(str(t_end)[:4])
                overlap = max(0, min(e, req_time[1]) - max(s, req_time[0]))
                need = req_time[1] - req_time[0]
                br["time"] = min(1.0, overlap / max(need, 1))
                if overlap < need:
                    limitations.append(f"time coverage {s}-{e} does not fully cover requested {req_time[0]}-{req_time[1]}")
            except ValueError:
                br["time"] = 0.3
                unknowns.append("time coverage unparseable")
        else:
            br["time"] = 0.3
            unknowns.append("time coverage unknown")

        # geography
        cgeo = set(c.get("geography") or [])
        if req_geo & cgeo or "global" in cgeo or "world" in cgeo:
            br["geography"] = 1.0
        elif cgeo:
            br["geography"] = 0.3
            limitations.append(f"geography {sorted(cgeo)} may not match request")
        else:
            br["geography"] = 0.3
            unknowns.append("geographic coverage unknown")

        # source trust
        trust = TRUST.get(reg_rec.trust_class if reg_rec else "community", 0.3)
        br["source_trust"] = trust
        if reg_rec and reg_rec.trust_class in ("official", "international"):
            reasons.append(f"trusted source class: {reg_rec.trust_class}")
        if c.get("provider_id") == "kaggle" or (reg_rec and reg_rec.trust_class == "commercial"):
            limitations.append("community/commercial upload — not an official statistical source")

        # doi
        br["doi_publication"] = 1.0 if c.get("doi") else 0.0
        if c.get("doi"):
            reasons.append("has DOI (publication-linked)")

        # license — UNKNOWN never open (A5)
        lic = (c.get("license") or "UNKNOWN")
        if lic.upper() == "UNKNOWN":
            br["license"] = 0.0
            unknowns.append("license UNKNOWN — treated as NOT open until verified")
            limitations.append("license unknown; verify before redistribution")
        elif OPEN_LICENSES.search(lic):
            br["license"] = 1.0
            reasons.append(f"open license: {lic}")
        else:
            br["license"] = 0.4
            limitations.append(f"license terms require review: {lic}")

        # access
        access = c.get("access_mode") or "UNKNOWN"
        br["access"] = {"PUBLIC_ANONYMOUS_API": 1.0, "PUBLIC_ANONYMOUS_HTTP": 0.9}.get(access, 0.4)
        if c.get("requires_login"):
            br["access"] = 0.4
            limitations.append("requires login/account")
        if c.get("restricted"):
            limitations.append("restricted data — user intervention likely")

        # documentation
        desc_len = len(c.get("description") or "")
        br["documentation"] = min(1.0, desc_len / 400)
        if desc_len < 40:
            unknowns.append("thin documentation/metadata")

        br = {k: round(v, 3) for k, v in br.items()}
        c["recommendation"] = br
        # weights: hard-ish constraints (variables/unit/time) dominate; trust boosts
        weights = {
            "topic": 0.5, "variables": 3.0, "unit": 1.5, "time": 1.5, "geography": 1.0,
            "source_trust": 1.6, "doi_publication": 0.6, "license": 0.8, "access": 1.2, "documentation": 0.4,
        }
        c["score"] = round(sum(br[k] * w for k, w in weights.items()) / sum(weights.values()), 4)
        c["reasons"] = (c.get("reasons") or []) + reasons
        c["limitations"] = (c.get("limitations") or []) + limitations
        c["unknowns"] = (c.get("unknowns") or []) + unknowns
        if trust_req == "official_first" and trust < 0.7:
            c["limitations"].append("user prefers official/international sources; this is a lower-trust source")
    candidates.sort(key=lambda x: -(x.get("score") or 0))
    return candidates
