"""Validation framework (P14-001..006, A30): every check emits code/severity/message/field/remediation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.db.repository import REPO
from app.domain.enums import Severity


def _add(build_id: str, code: str, severity: str, message: str, field: str | None = None, affected: int | None = None, remediation: str | None = None, details: dict | None = None) -> dict:
    rec = {"code": code, "severity": severity, "message": message, "field": field, "affected_rows": affected, "remediation": remediation, "details": details or {}}
    REPO.add_validation(build_id=build_id, **rec)
    return rec


def run_validations(df: pd.DataFrame, build_id: str, *, keys: list[str] | None = None, join_report: dict | None = None, expected_row_count: int | None = None, expected_schema: dict | None = None, imputation_stats: dict | None = None) -> list[dict]:
    out: list[dict] = []

    # canonicalize key names to the final frame (country→iso3) and keep only existing columns
    if keys:
        key_canon = {"country": "iso3", "country_name": "iso3", "nation": "iso3"}
        keys = [key_canon.get(k, k) for k in keys]
        keys = [k for k in keys if k in df.columns]

    # key uniqueness
    if keys:
        dup = int(df.dropna(subset=keys).duplicated(subset=keys).sum())
        if dup:
            out.append(_add(build_id, "KEY_DUPLICATE", Severity.ERROR, f"{dup} duplicate key rows on {keys}", field=",".join(keys), affected=dup, remediation="aggregate or deduplicate keys before export"))
        else:
            out.append(_add(build_id, "KEY_UNIQUE", Severity.INFO, f"keys {keys} unique", field=",".join(keys)))

    # duplicate rows
    dup_rows = int(df.duplicated().sum())
    if dup_rows:
        out.append(_add(build_id, "DUPLICATE_ROWS", Severity.WARNING, f"{dup_rows} fully duplicated rows", affected=dup_rows, remediation="review duplicates; drop if truly identical observations"))

    # missing per column
    for col in df.columns:
        mr = float(df[col].isna().mean())
        if mr > 0.5:
            out.append(_add(build_id, "MISSING_HIGH", Severity.WARNING, f"column {col} has {mr:.0%} missing", field=str(col), affected=int(df[col].isna().sum()), remediation="consider a missing policy (documented) or drop the column"))
        elif mr > 0:
            out.append(_add(build_id, "MISSING", Severity.INFO, f"column {col} missing {mr:.1%}", field=str(col)))

    # impossible values / outliers on numeric columns
    for col in df.select_dtypes(include=[np.number]).columns:
        s = df[col].dropna()
        if s.empty:
            continue
        neg = col.lower() in ("gdp_per_capita", "population", "youth_unemployment_rate", "unemployment_rate", "age", "income") and int((s < 0).sum())
        if neg:
            out.append(_add(build_id, "IMPOSSIBLE_VALUE", Severity.ERROR, f"{neg} negative values in {col}", field=str(col), affected=neg, remediation="check units/sign conventions"))
        if pd.api.types.is_numeric_dtype(s) and s.std() and abs(s.mean()) > 1e-9:
            z = ((s - s.mean()) / s.std()).abs()
            outliers = int((z > 6).sum())
            if outliers:
                out.append(_add(build_id, "OUTLIER", Severity.WARNING, f"{outliers} extreme outliers (|z|>6) in {col}", field=str(col), affected=outliers, remediation="inspect source records; do not delete silently"))

    # temporal gaps per entity group (only when the entity key actually exists in the frame)
    if keys:
        canon = {"country": "iso3", "country_name": "iso3"}
        year_col = next((c for c in df.columns if str(c).lower() == "year"), None)
        entity_key = next((canon.get(k, k) for k in keys if canon.get(k, k) in df.columns), None)
        if year_col and entity_key:
            y = pd.to_numeric(df[year_col], errors="coerce").dropna()
            if not y.empty:
                full = set(range(int(y.min()), int(y.max()) + 1))
                gaps = 0
                for _, grp in df.groupby(entity_key):
                    gy = set(pd.to_numeric(grp[year_col], errors="coerce").dropna().astype(int))
                    gaps += len(full - gy)
                if gaps:
                    out.append(_add(build_id, "TEMPORAL_GAP", Severity.WARNING, f"{gaps} entity-years missing from the balanced range", affected=gaps, remediation="document coverage or use missing policy"))
                else:
                    out.append(_add(build_id, "TEMPORAL_COMPLETE", Severity.INFO, "no temporal gaps in range"))

    # join coverage / unmatched
    if join_report:
        cov = join_report.get("left_coverage")
        if cov is not None and cov < 0.8:
            out.append(_add(build_id, "JOIN_COVERAGE_LOW", Severity.WARNING, f"join left coverage {cov:.0%} < 80%", affected=join_report.get("unmatched_left"), remediation="inspect unmatched entities", details=join_report))
        else:
            out.append(_add(build_id, "JOIN_COVERAGE", Severity.INFO, f"join coverage {cov}", details=join_report))
        unmatched = join_report.get("unmatched_left", 0)
        if unmatched:
            out.append(_add(build_id, "UNMATCHED_ENTITIES", Severity.INFO, f"{unmatched} unmatched left entities; samples: {join_report.get('unmatched_samples', [])[:5]}", affected=unmatched))

    # row count drift
    if expected_row_count is not None and abs(len(df) - expected_row_count) > max(10, expected_row_count * 0.1):
        out.append(_add(build_id, "ROW_COUNT_DRIFT", Severity.ERROR, f"row count {len(df)} deviates from expected {expected_row_count}", affected=len(df)))
    elif expected_row_count is not None:
        out.append(_add(build_id, "ROW_COUNT_STABLE", Severity.INFO, f"row count {len(df)} within tolerance of {expected_row_count}"))

    # constant columns
    for col in df.columns:
        if df[col].nunique(dropna=True) <= 1 and len(df) > 1:
            out.append(_add(build_id, "CONSTANT_COLUMN", Severity.WARNING, f"column {col} is constant", field=str(col), remediation="verify whether the constant is expected"))

    # type drift
    if expected_schema:
        for col, dtype in expected_schema.items():
            if col in df.columns and str(df[col].dtype) != dtype:
                out.append(_add(build_id, "TYPE_DRIFT", Severity.ERROR, f"column {col} type changed {dtype} -> {df[col].dtype}", field=str(col), remediation="re-check upstream transform"))

    # imputation transparency
    if imputation_stats and imputation_stats.get("imputed_cells", 0) > 0:
        out.append(_add(build_id, "IMPUTATION_PRESENT", Severity.INFO, f"{imputation_stats['imputed_cells']} values imputed via {imputation_stats.get('method')} ({imputation_stats.get('imputed_ratio'):.1%} of missing); mask exported", details=imputation_stats))

    return out
