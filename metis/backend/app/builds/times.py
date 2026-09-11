"""Time normalization & alignment (P13-009..012, A25) + frequency conflict checks.

year/quarter/month/day recognized; FY2020 (fiscal) is NOT silently treated as a
calendar year; month→year aggregation must be explicit and is recorded in
provenance by the caller.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.errors import MetisError


@dataclass
class TimeValue:
    granularity: str  # year | quarter | month | day | fiscal_year
    year: int
    quarter: int | None = None
    month: int | None = None
    day: int | None = None
    fiscal: bool = False
    raw: str = ""
    note: str = ""


def parse_time_value(raw) -> TimeValue | None:
    """Parse any supported time expression. Returns None for unparseable (caller flags)."""
    if raw is None:
        return None
    s = str(raw).strip()
    # 2020 / "2020年"
    m = re.fullmatch(r"(20\d\d|19\d\d)\s*年?", s)
    if m:
        return TimeValue("year", int(m.group(1)), raw=s)
    # 2020-01-01 / 2020/01/01
    m = re.fullmatch(r"(20\d\d|19\d\d)[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return TimeValue("day", int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)), raw=s)
    # 2020Q1 / 2020-Q1 / 2020年1季度
    m = re.fullmatch(r"(20\d\d|19\d\d)\s*[-/Q季度]*\s*([1-4])\s*季?度?Q?", s, re.I)
    if m and ("q" in s.lower() or "季" in s):
        return TimeValue("quarter", int(m.group(1)), quarter=int(m.group(2)), raw=s)
    # 2020-03 / 2020/03 / 2020年3月
    m = re.fullmatch(r"(20\d\d|19\d\d)\s*年?\s*[-/]?\s*(\d{1,2})\s*月?", s)
    if m:
        month = int(m.group(2))
        if 1 <= month <= 12:
            return TimeValue("month", int(m.group(1)), month=month, raw=s)
    # FY2020 / 2020财年 — fiscal year, NOT calendar (A25)
    m = re.fullmatch(r"(?:FY|fy|财年)\s*(20\d\d|19\d\d)(?:/(\d\d))?", s)
    if m:
        return TimeValue("fiscal_year", int(m.group(1)), fiscal=True, raw=s, note="fiscal year — check fiscal calendar before treating as calendar year")
    # 2020W12 weeks unsupported
    return None


def detect_frequency(values: list) -> str:
    counts = {"year": 0, "quarter": 0, "month": 0, "day": 0, "fiscal_year": 0, "unknown": 0}
    for v in values:
        tv = parse_time_value(v)
        if tv is None:
            counts["unknown"] += 1
        else:
            counts[tv.granularity] += 1
    known = {k: c for k, c in counts.items() if k != "unknown"}
    if sum(known.values()) == 0:
        return "unknown"
    return max(known, key=known.get)


def check_frequency_conflict(freq_a: str, freq_b: str) -> dict:
    """Different frequencies must not merge without explicit alignment (A25/PRD §23)."""
    if freq_a == freq_b or "unknown" in (freq_a, freq_b):
        return {"conflict": False, "needs_alignment": freq_a == "unknown" or freq_b == "unknown"}
    return {"conflict": True, "needs_alignment": True, "from": freq_a, "to": freq_b, "message": f"frequency conflict: {freq_a} vs {freq_b}; explicit aggregation/annualization required"}


def aggregate_to_year(df, time_col: str, value_cols: list[str], method: str = "mean") -> tuple[object, dict]:
    """Explicit month/quarter→year aggregation with provenance record (A25).

    Returns (agg_df, provenance_record). method: mean | sum | last.
    """
    if method not in ("mean", "sum", "last", "min", "max"):
        raise MetisError("TIME_FREQUENCY_CONFLICT", f"unsupported aggregation method {method}")

    years = []
    for v in df[time_col]:
        tv = parse_time_value(v)
        if tv is None or tv.granularity not in ("month", "quarter", "day"):
            years.append(None)
            continue
        years.append(tv.year)
    work = df.assign(__year=years).dropna(subset=["__year"])
    agg = getattr(work.groupby("__year")[value_cols], method)()
    agg = agg.reset_index().rename(columns={"__year": time_col})
    prov = {
        "operation": "time_aggregation",
        "from_frequency": detect_frequency(df[time_col].tolist()),
        "to_frequency": "year",
        "method": method,
        "rows_before": int(len(df)),
        "rows_after": int(len(agg)),
        "note": f"aggregated sub-year periods to years using {method}",
    }
    return agg, prov


def annualize_fiscal(df, time_col: str, rule: str = "start_year") -> tuple[object, dict]:
    """FY2020 → 2020 (start-year rule) — explicit, provenance-recorded."""
    work = df.copy()
    conv = []
    for v in work[time_col]:
        tv = parse_time_value(v)
        conv.append(tv.year if tv and tv.fiscal else None)
    work[time_col] = conv
    prov = {"operation": "fiscal_annualization", "rule": rule, "note": "FY mapped to starting calendar year; verify fiscal calendar with data owner", "rows": int(len(work))}
    return work, prov
