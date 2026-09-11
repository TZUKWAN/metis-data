"""Dataset Profile (P12, A21) + Variable Semantics (P12-008/009, A22).

Profiling is chunked for large files (100MB+ must not OOM; no full-DataFrame
copies). Semantic layer distinguishes same-name/different-meaning columns
(current vs constant price, percentage vs fraction, 0/1 vs M/F codings).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.errors import MetisError
from app.core.logging import get_logger
from app.datasets.parsers import ParsedTable, parse_table
from app.domain.schemas import VariableSemantic

log = get_logger("profile")

CHUNK_ROWS = 200_000
PREVIEW_ROWS = 20
MAX_SAMPLE_FOR_UNIQUE = 1_000_000


def profile_artifact(artifact_id: str, raw_rel_path: str, *, persist: bool = True) -> dict:
    from app.core.paths import raw_root

    path = raw_root() / raw_rel_path
    prof = profile_file(path)
    if persist:
        from app.db.models import ArtifactRow
        from app.db.session import new_session

        with new_session() as s:
            row = s.get(ArtifactRow, artifact_id)
            if row is not None:
                row.profile_json = prof
                row.status = "PROFILED"
                s.commit()
    return prof


def profile_file(path: Path) -> dict:
    parsed = parse_table(path)
    fmt = parsed.fmt
    prof: dict[str, Any] = {
        "file": path.name,
        "format": fmt,
        "size_bytes": path.stat().st_size,
        "meta": parsed.meta,
        "profiled_at": datetime.now(UTC).isoformat(),
    }
    # non-tabular formats: schema-level profile only
    if fmt in ("NETCDF",):
        prof.update({"dimensions": parsed.meta.get("dimensions"), "variables": parsed.meta.get("variables")})
        return prof
    if fmt in ("GEOJSON", "SHP"):
        df = parsed.df
        prof.update({"row_count": int(len(df)), "column_count": int(df.shape[1]), "crs": parsed.meta.get("crs"), "geometry_types": parsed.meta.get("geometry_types"), "schema": _schema(df.head(1000))})
        return prof

    # tabular: chunked accumulation (memory-bounded)
    df_all = None
    if path.stat().st_size < 32 * 1024 * 1024:
        df_all = parsed.df  # small: direct
        n_rows = len(df_all)
        chunks = [df_all]
    else:
        n_rows = 0
        chunks = []
        for chunk in _iter_chunks(path, parsed):
            chunks.append(chunk)
            n_rows += len(chunk)
            if sum(len(c) for c in chunks) > MAX_SAMPLE_FOR_UNIQUE:
                chunks = chunks[-3:]

    sample_df = pd.concat(chunks, ignore_index=True) if len(chunks) > 1 else (chunks[0] if chunks else parsed.df)
    prof.update(
        {
            "row_count": int(n_rows if df_all is None else len(df_all)),
            "column_count": int(sample_df.shape[1]),
            "columns": [str(c) for c in sample_df.columns],
            "schema": _schema(sample_df),
            "sample": json.loads(sample_df.head(PREVIEW_ROWS).to_json(orient="records", force_ascii=False, date_format="iso")),
            "duplicate_row_count": int(sample_df.duplicated().sum()),
            "profile_mode": "full" if df_all is not None else "chunked_sample",
        }
    )
    prof["likely"] = _guess_roles(sample_df, prof["schema"])
    # labels from stat formats
    labels = sample_df.attrs.get("variable_labels") or {}
    value_labels = sample_df.attrs.get("value_labels") or {}
    if labels:
        prof["variable_labels"] = {k: str(v) for k, v in labels.items() if v}
    if value_labels:
        prof["value_labels"] = {k: {str(kk): str(vv) for kk, vv in v.items()} for k, v in value_labels.items() if isinstance(v, dict)}
    return prof


def _iter_chunks(path: Path, parsed: ParsedTable):
    if parsed.fmt in ("CSV", "TSV", "TXT"):
        sep = "\t" if parsed.fmt == "TSV" else None
        reader = pd.read_csv(path, chunksize=CHUNK_ROWS, sep=sep, engine="python")
        yield from reader
    elif parsed.fmt == "PARQUET":
        pf = pd.read_parquet(path)
        for i in range(0, len(pf), CHUNK_ROWS):
            yield pf.iloc[i: i + CHUNK_ROWS]
        del pf
    elif parsed.fmt == "JSONL":
        with path.open(encoding="utf-8", errors="ignore") as f:
            buf = []
            for line in f:
                if line.strip():
                    buf.append(json.loads(line))
                if len(buf) >= CHUNK_ROWS:
                    yield pd.json_normalize(buf)
                    buf = []
            if buf:
                yield pd.json_normalize(buf)
    else:
        yield parsed.df


def _schema(df: pd.DataFrame) -> list[dict]:
    """P16-001..007: extended per-column profile (quantiles, cardinality, pattern,
    language hints, categorical candidates, unit/rate/currency/price hints)."""
    import re as _re

    out = []
    n = max(len(df), 1)
    for col in df.columns:
        s = df[col]
        numeric = pd.api.types.is_numeric_dtype(s)
        entry = {
            "name": str(col),
            "dtype": str(s.dtype),
            "nullable": bool(s.isna().any()),
            "missing_rate": round(float(s.isna().mean()), 4),
            "unique": int(s.nunique(dropna=True)),
            "cardinality_ratio": round(float(s.nunique(dropna=True)) / n, 4),
            "numeric": numeric,
        }
        if numeric:
            desc = s.describe()
            entry["min"] = _safe(desc.get("min"))
            entry["max"] = _safe(desc.get("max"))
            entry["mean"] = _safe(desc.get("mean"))
            try:
                q = s.quantile([0.25, 0.5, 0.75])
                entry["quantiles"] = {"q25": _safe(q.get(0.25)), "q50": _safe(q.get(0.5)), "q75": _safe(q.get(0.75))}
            except Exception:  # noqa: BLE001
                entry["quantiles"] = None
            cl = str(col).lower()
            if any(k in cl for k in ("percent", "rate", "share", "ratio", "%")):
                entry["unit_hint"] = "percent-or-fraction"
                if entry.get("max") is not None and float(entry["max"]) <= 1.5:
                    entry["unit_hint"] = "fraction"
            if any(k in cl for k in ("usd", "gdp", "income", "price", "gdp_pc")):
                entry["currency_hint"] = "currency-like (check current vs constant price)"
            if any(k in cl for k in ("per_1000", "per1000", "per_100k", "per_100_000")):
                entry["rate_basis_hint"] = "per-1000/per-100k"
        else:
            vc = s.dropna().astype(str).value_counts()
            entry["top_values"] = {k: int(v) for k, v in vc.head(5).items()}
            sample = s.dropna().astype(str).head(50)
            if len(sample):
                digitish = sum(1 for v in sample if _re.fullmatch(r"[\d.,\-]+", v))
                cjk = sum(1 for v in sample if _re.search(r"[一-鿿]", v))
                entry["pattern"] = "numeric-string" if digitish > len(sample) * 0.8 else "text"
                entry["language_hint"] = "contains-CJK" if cjk > len(sample) * 0.2 else "latin-or-other"
            if 1 < entry["unique"] <= 20:
                entry["categorical_candidate"] = True
        out.append(entry)
    return out


def _safe(v):
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 6)
    except (TypeError, ValueError):
        return None


def _guess_roles(df: pd.DataFrame, schema: list[dict]) -> dict:
    """likely key / time / geography / id detection (A21)."""
    roles: dict[str, list[str]] = {"likely_key": [], "likely_time": [], "likely_geography": [], "likely_id": []}
    name_map = {c["name"]: c for c in schema}
    for col in df.columns:
        cl = str(col).lower()
        s = df[col]
        entry = name_map.get(str(col), {})
        if cl in ("year", "年份") or (cl.endswith("_year") or "year" == cl.split("_")[-1]) or cl in ("date", "日期", "time", "period", "quarter", "month"):
            roles["likely_time"].append(str(col))
        if cl in ("country", "iso3", "iso2", "country_code", "国家", "province", "省", "city", "城市", "region", "geo", "geo_id") or "country" in cl or "iso" in cl:
            roles["likely_geography"].append(str(col))
        if cl in ("id", "uid", "objectid", "fid") or cl.endswith("_id") or cl.endswith("id".lower()) and entry.get("numeric"):
            roles["likely_id"].append(str(col))
        # key candidate: no missing, all unique
        if entry.get("unique") == len(df) and not entry.get("nullable"):
            roles["likely_key"].append(str(col))
    return roles


# ---------------- Variable Semantics (A22) ----------------
UNIT_SYNONYMS = {
    "percent": {"percent", "percentage", "%", "pct", "rate_pct", "百分比"},
    "fraction": {"fraction", "ratio", "share", "proportion", "比例"},
    "usd": {"usd", "us_dollar", "constant_usd", "current_usd", "dollar"},
    "local_currency": {"lcu", "local_currency", "national_currency"},
}


class SemanticConflict(MetisError):
    def __init__(self, message: str, details: dict) -> None:
        super().__init__("SEMANTIC_CONFLICT", message, details=details)


def build_variable_semantic(canonical_name: str, original_name: str, *, unit: str = "UNKNOWN", scale: str = "UNKNOWN", coding: dict | None = None, frequency: str = "UNKNOWN", geography_level: str = "UNKNOWN", population: str = "UNKNOWN", price_basis: str = "UNKNOWN", currency: str = "UNKNOWN", base_year: int | None = None, source_dataset: str = "", source_field: str = "", confidence: float = 0.0) -> VariableSemantic:
    return VariableSemantic(
        canonical_name=canonical_name,
        original_name=original_name,
        display_name=canonical_name.replace("_", " ").title(),
        unit=unit,
        scale=scale,
        coding=coding,
        frequency=frequency,
        geography_level=geography_level,
        population=population,
        price_basis=price_basis,
        currency=currency,
        base_year=base_year,
        source_dataset=source_dataset,
        source_field=source_field,
        confidence=confidence,
    )


def compare_semantics(a: VariableSemantic, b: VariableSemantic) -> dict:
    """Same-name ≠ same-meaning. Returns compatibility + required conversions."""
    issues: list[str] = []
    conversions: list[dict] = []
    compatible = True

    # unit: percent vs fraction convertible with formula
    ua, ub = a.unit.lower(), b.unit.lower()
    if ua != ub:
        pair = {ua, ub}
        if pair <= {"percent", "fraction"}:
            conversions.append({"kind": "unit", "from": ub, "to": ua, "formula": "x * 100" if ua == "percent" else "x / 100"})
        else:
            compatible = False
            issues.append(f"unit mismatch: {ua} vs {ub}; no verified conversion")
    # price basis: current vs constant NOT mergeable silently
    if a.price_basis != b.price_basis and "UNKNOWN" not in (a.price_basis, b.price_basis):
        compatible = False
        issues.append(f"price basis differs: {a.price_basis} vs {b.price_basis} (current vs constant requires deflator; refused)")
    if a.base_year != b.base_year and (a.base_year or b.base_year):
        compatible = False
        issues.append(f"constant-price base year differs: {a.base_year} vs {b.base_year}")
    if a.currency != b.currency and "UNKNOWN" not in (a.currency, b.currency):
        compatible = False
        issues.append(f"currency differs: {a.currency} vs {b.currency}; needs fx conversion policy")
    # coding differences: alignable via explicit mapping
    if a.coding and b.coding and a.coding != b.coding:
        mapping = _align_codings(a.coding, b.coding)
        if mapping:
            conversions.append({"kind": "coding", "mapping": mapping})
        else:
            compatible = False
            issues.append(f"category codings not alignable: {a.coding} vs {b.coding}")
    if a.frequency != b.frequency and "UNKNOWN" not in (a.frequency, b.frequency):
        issues.append(f"frequency differs: {a.frequency} vs {b.frequency} — explicit aggregation required before join")
    if a.population != b.population and "UNKNOWN" not in (a.population, b.population):
        issues.append(f"population differs: {a.population} vs {b.population}")
    return {"compatible": compatible, "issues": issues, "conversions": conversions}


def _align_codings(ca: dict, cb: dict) -> dict | None:
    """Explicit mapping between two codings of the same concept, e.g. {0:male,1:female} vs {M:male,F:female}."""
    a_to_concept = {str(k): str(v).lower() for k, v in ca.items()}
    b_to_concept = {str(k): str(v).lower() for k, v in cb.items()}
    concept_to_b: dict[str, str] = {}
    for k, v in b_to_concept.items():
        concept_to_b.setdefault(v, k)
    mapping = {}
    for ak, concept in a_to_concept.items():
        if concept in concept_to_b:
            mapping[ak] = concept_to_b[concept]
    return mapping or None
