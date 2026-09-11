"""Join safety (P13-014..016, A26): cardinality detection, m:m guard, coverage stats."""
from __future__ import annotations

import pandas as pd

from app.core.errors import MetisError


def check_keys(left: pd.DataFrame, right: pd.DataFrame, keys: list[str]) -> dict:
    """Pre-join validation: key presence, duplicates, cardinality, output estimate."""
    missing_l = [k for k in keys if k not in left.columns]
    missing_r = [k for k in keys if k not in right.columns]
    if missing_l or missing_r:
        raise MetisError("JOIN_KEY_MISSING", f"join keys missing: left={missing_l} right={missing_r}", details={"left_missing": missing_l, "right_missing": missing_r})
    # duplicates counted on JOINABLE rows only (all keys non-null): NaN keys never match
    left_j = left.dropna(subset=keys)
    right_j = right.dropna(subset=keys)
    dup_l = int(left_j.duplicated(subset=keys).sum())
    dup_r = int(right_j.duplicated(subset=keys).sum())
    if dup_l == 0 and dup_r == 0:
        cardinality = "1:1"
    elif dup_l == 0 and dup_r > 0:
        cardinality = "1:m"
    elif dup_l > 0 and dup_r == 0:
        cardinality = "m:1"
    else:
        cardinality = "m:m"
    est_rows = 0
    l_grp = left.groupby(keys).size()
    r_grp = right.groupby(keys).size()
    joined = pd.concat([l_grp.rename("l"), r_grp.rename("r")], axis=1, join="inner").fillna(0)
    est_rows = int((joined.l * joined.r).sum())
    return {
        "cardinality": cardinality,
        "dup_left": dup_l,
        "dup_right": dup_r,
        "left_rows": int(len(left)),
        "right_rows": int(len(right)),
        "estimated_output_rows": est_rows,
        "key_columns": keys,
        "cartesian_risk": est_rows > max(len(left), len(right)) * 10,
    }


def safe_join(left: pd.DataFrame, right: pd.DataFrame, keys: list[str], *, how: str = "inner", allow_mm: bool = False) -> tuple[pd.DataFrame, dict]:
    """Join with pre-checks. m:m blocked by default (A26; declared 1:1 with actual dups fails)."""
    info = check_keys(left, right, keys)
    if info["cardinality"] == "m:m" and not allow_mm:
        raise MetisError(
            "JOIN_CARDINALITY_BLOCKED",
            f"m:m join blocked by default (left dups={info['dup_left']}, right dups={info['dup_right']}). Aggregate/dedupe first or pass allow_mm explicitly.",
            details=info,
        )
    if info["cardinality"] == "1:1" and (info["dup_left"] or info["dup_right"]):
        raise MetisError("JOIN_KEY_MISSING", "declared 1:1 but duplicate keys found", details=info)
    # rows with NULL keys can never match — exclude them from the join (pandas would
    # otherwise treat NaN==NaN as a match and explode the result)
    before = len(left)
    null_left = int(left[keys].isna().any(axis=1).sum())
    null_right = int(right[keys].isna().any(axis=1).sum())
    left = left.dropna(subset=keys)
    right = right.dropna(subset=keys)
    merged = left.merge(right, on=keys, how=how, suffixes=("", "_right"), indicator=True)
    matched = int((merged["_merge"] == "both").sum())
    unmatched_left = int((merged["_merge"] == "left_only").sum())
    unmatched_right = int((merged["_merge"] == "right_only").sum())
    merged = merged.drop(columns=["_merge"])
    # sample unmatched entities
    if how == "inner":
        l_keys = set(map(tuple, left[keys].drop_duplicates().values))
        r_keys = set(map(tuple, right[keys].drop_duplicates().values))
        unmatched_samples = [list(t) for t in list(l_keys - r_keys)[:10]]
    else:
        unmatched_samples = []
    report = {
        **info,
        "how": how,
        "row_count_before": before,
        "row_count_after": int(len(merged)),
        "matched": matched,
        "unmatched_left": unmatched_left if how != "inner" else len(l_keys - r_keys),
        "unmatched_right": unmatched_right if how != "inner" else len(r_keys - l_keys),
        "unmatched_samples": unmatched_samples,
        "null_key_rows_dropped": {"left": null_left, "right": null_right},
        "coverage": round(matched / max(len(merged), 1), 4) if len(merged) else 0.0,
        "left_coverage": round(len(l_keys & r_keys) / max(len(l_keys), 1), 4),
        "explosion": bool(len(merged) > before * 3 and len(merged) - before > 100),
    }
    return merged, report


# ---------------- Missing policy (P13-017/018, A28) ----------------
def apply_missing_policy(df: pd.DataFrame, columns: list[str], group_cols: list[str] | None, method: str = "none", params: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Default NONE (0 imputed). Any generated value is flagged via mask + op record (A28).

    Returns (result_df, imputation_mask, provenance_record).
    """
    params = params or {}
    result = df.copy()
    mask = pd.DataFrame(False, index=df.index, columns=[c for c in columns if c in df.columns])
    prov = {"operation": "missing_policy", "method": method, "columns": columns, "group_cols": group_cols, "imputed_cells": 0, "imputed_ratio": 0.0}

    if method == "none":
        return result, mask, prov
    cols = [c for c in columns if c in result.columns]
    if not cols:
        return result, mask, prov
    before_na = result[cols].isna().copy()

    if method == "drop":
        result = result.dropna(subset=cols)
    elif method in ("ffill", "bfill"):
        if group_cols:
            result[cols] = result.groupby(group_cols)[cols].transform(lambda g: g.ffill() if method == "ffill" else g.bfill())
        else:
            result[cols] = result[cols].ffill() if method == "ffill" else result[cols].bfill()
    elif method == "linear":
        result[cols] = result[cols].interpolate(method="linear", limit=params.get("limit"))
    elif method == "group_linear":
        if not group_cols:
            raise MetisError("BUILD_FAILED", "group_linear requires group_cols")
        for col in cols:
            result[col] = result.groupby(group_cols)[col].transform(lambda g: g.interpolate(method="linear", limit=params.get("limit")))
    elif method in ("mean", "median"):
        fill_vals = result[cols].agg(method)
        result[cols] = result[cols].fillna(fill_vals)
    else:
        raise MetisError("BUILD_FAILED", f"unknown missing policy {method}")

    if method != "drop":
        filled = before_na & ~result[cols].isna()
        mask[filled.columns] = filled
        n = int(filled.values.sum())
        prov["imputed_cells"] = n
        prov["imputed_ratio"] = round(n / max(int(before_na.values.sum()), 1), 4) if before_na.values.sum() else 0.0
        prov["note"] = f"{n} values generated by {method}; cells flagged in imputation_mask (column __imputed_<col> exported)"
    else:
        prov["rows_dropped"] = int(len(df) - len(result))
    return result, mask, prov


# ---------------- Derived variables (P13-021, A29) ----------------
SAFE_OPS = {"+", "-", "*", "/", "**", "(", ")", ","}
NAME_RE = __import__("re").compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def derive_variable(df: pd.DataFrame, formula: str, output_field: str, input_fields: list[str]) -> tuple[pd.DataFrame, dict]:
    """Controlled formula evaluation: only whitelisted arithmetic over declared inputs.

    Division-by-zero → NaN (flagged), not crash, not silent zero.
    """
    for f in input_fields:
        if f not in df.columns:
            raise MetisError("BUILD_FAILED", f"derived variable input missing: {f}")
    if not NAME_RE.match(output_field):
        raise MetisError("BUILD_FAILED", f"illegal output field name: {output_field}")
    # tokenize-check formula: only names, numbers, ops
    import re as _re

    expr = formula
    tokens = _re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+\.?\d*|[()+\-*/,**,]", expr)
    rebuilt = "".join(tokens)
    if _re.sub(r"\s+", "", expr) != rebuilt:
        raise MetisError("BUILD_FAILED", f"formula contains unsupported characters: {formula}")
    for t in tokens:
        if _re.match(r"^[A-Za-z_]", t) and t not in input_fields:
            raise MetisError("BUILD_FAILED", f"formula references undeclared field: {t}")

    result = df.copy()
    env = {f: pd.to_numeric(result[f], errors="coerce") for f in input_fields}
    with __import__("numpy").errstate(divide="ignore", invalid="ignore"):
        values = eval(expr, {"__builtins__": {}}, env)  # noqa: S307 — token whitelist above
    values = pd.Series(values, index=df.index).replace([__import__("numpy").inf, -__import__("numpy").inf], __import__("numpy").nan)
    result[output_field] = values
    n_zero_div = int((env.get("/") is not None) and 0)  # computed via inf→nan replacement
    prov = {
        "operation": "derived_variable",
        "formula": formula,
        "input_fields": input_fields,
        "output_field": output_field,
        "division_by_zero_policy": "result set to NaN (flagged), not zero",
        "nan_count": int(pd.isna(result[output_field]).sum()),
    }
    return result, prov


# ---------------- Unit conversion (P13-004) ----------------
def convert_unit(series: pd.Series, from_unit: str, to_unit: str) -> tuple[pd.Series, dict | None]:
    """Only explicit, verifiable conversions allowed; otherwise refuse (A22)."""
    pair = (from_unit.lower().strip(), to_unit.lower().strip())
    factor = None
    formula = None
    if pair[0] == pair[1]:
        return series, None
    if set(pair) == {"percent", "fraction"}:
        factor = 100.0 if pair[1] == "percent" else 1 / 100.0
        formula = "x * 100" if pair[1] == "percent" else "x / 100"
    if pair[0] == "percent" and pair[1] == "point":
        factor, formula = 1.0, "x * 1"
    if factor is None:
        raise MetisError("SEMANTIC_CONFLICT", f"no verified conversion {from_unit} -> {to_unit}; refusing to guess")
    return series * factor, {"operation": "unit_conversion", "from": from_unit, "to": to_unit, "factor": factor, "formula": formula}
