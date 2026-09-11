"""Natural language requirement parsing (P10-001/002, A1).

Rule-based, deterministic parser: extracts research question, unit, geography,
time range, frequency, variable roles, source preferences; every inferred default
lands in `assumptions`; original raw_request is preserved verbatim.
"""
from __future__ import annotations

import re

from app.domain.schemas import DataRequirement, VariableRequest

UNIT_PATTERNS = [
    ("country", [r"\b国家层面\b", r"\b跨国\b", r"national level", r"\bcountries?\b", r"\bcountry-level\b", r"国际"]),
    ("individual", [r"\b个体\b", r"\b个人层面\b", r"individuals?\b", r"\brespondents?\b", r"大学生", r"住户"]),
    ("province", [r"省级", r"省层面", r"province-level", r"\bprovinces\b"]),
    ("prefecture", [r"地级", r"prefecture", r"城市层面"]),
    ("firm", [r"\bfirm-level\b", r"\bfirms\b", r"企业层面"]),
    ("year", [r"time series", r"时间序列"]),
]

FREQ_PATTERNS = [
    ("annual", [r"年度", r"annual", r"yearly", r"每年"]),
    ("quarterly", [r"季度", r"quarterly"]),
    ("monthly", [r"月度", r"monthly", r"每月"]),
    ("daily", [r"日度", r"daily"]),
]

SOURCE_PREF = [
    ("official", [r"官方", r"official"]),
    ("international_org", [r"国际组织", r"international organization", r"world bank|ilo|un |oecd|imf"]),
]

TASK_TYPE_PATTERNS = [
    ("panel", [r"面板", r"panel"]),
    ("cross_section", [r"截面", r"cross.section"]),
    ("time_series", [r"时间序列", r"time series"]),
    ("ml_training", [r"训练数据", r"training data", r"machine learning", r"机器学习"]),
]

VARIABLE_LEXICON = [
    # (canonical hint, role default, aliases)
    ("youth_unemployment_rate", "outcome", [r"青年失业", r"youth unemployment", r"young unemployment"]),
    ("unemployment_rate", "outcome", [r"失业率", r"unemployment rate"]),
    ("gdp_per_capita", "control", [r"人均\s*gdp", r"gdp\s*per\s*capita", r"per.capita gdp"]),
    ("gdp", "control", [r"\bgdp\b", r"国内生产总值", r"生产总值"]),
    ("education_level", "exposure", [r"教育水平", r"教育程度", r"education( level|al attainment)?", r"受教育程度"]),
    ("population", "control", [r"人口", r"population"]),
    ("inflation", "control", [r"通胀", r"inflation", r"cpi"]),
    ("trade_openness", "control", [r"贸易", r"trade openness"]),
    ("gpa", "outcome", [r"\bgpa\b", r"绩点"]),
    ("self_efficacy", "outcome", [r"自我效能", r"self.efficacy"]),
    ("engagement", "outcome", [r"学习投入", r"(study|learning) engagement"]),
    ("ai_usage", "exposure", [r"生成式\s*ai", r"generative ai", r"ai 使用", r"chatgpt"]),
]

GEO_HINTS = [
    ("CN", [r"中国", r"\bChina\b"]),
    ("US", [r"美国", r"\bUnited States\b", r"\bUS\b"]),
    ("EU", [r"欧盟", r"\bEU\b", r"european"]),
    ("global", [r"全球", r"global", r"世界", r"跨国"]),
]


def parse_requirement(text: str) -> DataRequirement:
    t = text.strip()
    req = DataRequirement(raw_request=t)
    assumptions: list[str] = []
    tl = t.lower()

    # research question / goal = the whole sentence minus delivery instructions
    req.goal = re.sub(r"^构建|^请|^帮我|构建|生成|下载|交付.*$", "", t)[:400] or t[:400]
    req.research_question = req.goal

    # unit of analysis
    for unit, pats in UNIT_PATTERNS:
        if any(re.search(p, tl) for p in pats):
            req.unit_of_analysis = unit
            break
    if not req.unit_of_analysis:
        req.unit_of_analysis = "unknown"
        assumptions.append("unit_of_analysis='unknown' — could not infer from request; please confirm")

    # time range: 2015—2023 / 2015-2023 / 2015 to 2023 / since 2015
    m = re.search(r"(20\d\d)\s*[—\-–~至to]+\s*(20\d\d)", tl)
    if m:
        req.time_range = (int(m.group(1)), int(m.group(2)))
    else:
        m2 = re.search(r"(?:since|自|从)\s*(20\d\d)", tl)
        if m2:
            req.time_range = (int(m2.group(1)), 2026)
            assumptions.append(f"time_range end defaulted to {req.time_range[1]} (current year) because request said 'since {m2.group(1)}'")

    # frequency
    freq_found = False
    for freq, pats in FREQ_PATTERNS:
        if any(re.search(p, tl) for p in pats):
            req.frequency = freq
            freq_found = True
            break
    if not freq_found:
        if req.unit_of_analysis in ("country", "province", "prefecture") and req.time_range:
            req.frequency = "annual"
            assumptions.append("frequency='annual' inferred by default for macro panel request (shown explicitly)")
        else:
            req.frequency = "unknown"
            assumptions.append("frequency='unknown' — please confirm")

    # task type
    for task, pats in TASK_TYPE_PATTERNS:
        if any(re.search(p, tl) for p in pats):
            req.data_task_type = task
            break

    # variables by lexicon
    vars_ = VariableRequest()
    role_field = {"outcome": "outcomes", "exposure": "exposures", "mediator": "mediators", "moderator": "moderators", "control": "controls", "identifier": "identifiers"}
    for canonical, role, pats in VARIABLE_LEXICON:
        if any(re.search(p, tl) for p in pats):
            getattr(vars_, role_field[role]).append(canonical)
    req.variables = vars_

    # source preference
    for src, pats in SOURCE_PREF:
        if any(re.search(p, tl) for p in pats):
            req.preferred_sources.append(src)
    if not req.preferred_sources:
        req.preferred_sources = []
    # trust requirement default from preferred_sources
    if "official" in req.preferred_sources or "international_org" in req.preferred_sources:
        req.trust_requirement = "official_first"
        assumptions.append("trust_requirement='official_first' derived from preferred source mention")

    # geography
    for geo, pats in GEO_HINTS:
        if any(re.search(p, tl) for p in pats):
            req.geography.append(geo)
    if "global" in req.geography or (req.unit_of_analysis == "country" and not req.geography):
        if "global" not in req.geography:
            req.geography.append("global")

    # deliverable/format preferences
    fmt = []
    for f, pat in [("csv", r"\bcsv\b"), ("parquet", r"parquet"), ("xlsx", r"xlsx|excel"), ("report", r"数据说明|质量报告|说明|report"), ("reproducible", r"可复现|reproduc")]:
        if re.search(pat, tl):
            fmt.append(f)
    if fmt:
        req.notes = f"deliverables requested: {', '.join(fmt)}"
    if "panel" not in tl and req.time_range and req.unit_of_analysis == "country":
        req.data_task_type = req.data_task_type if req.data_task_type != "panel" else "panel"

    req.assumptions = assumptions
    return req


def validate_requirement(req: DataRequirement) -> list[dict]:
    """P10-002: detect conflicts / infeasible constraints; return explainable errors."""
    problems = []
    if req.time_range:
        start, end = req.time_range
        if start > end:
            problems.append({"code": "REQUIREMENT_CONFLICT", "message": f"time range inverted: {start} > {end}", "field": "time_range"})
        if end > 2100 or start < 1900:
            problems.append({"code": "REQUIREMENT_CONFLICT", "message": f"time range out of plausible bounds: {start}-{end}", "field": "time_range"})
    if req.frequency not in ("annual", "quarterly", "monthly", "daily", "unknown"):
        problems.append({"code": "REQUIREMENT_CONFLICT", "message": f"unsupported frequency {req.frequency}", "field": "frequency"})
    if req.max_missing_rate is not None and not (0 <= req.max_missing_rate <= 1):
        problems.append({"code": "REQUIREMENT_CONFLICT", "message": f"max_missing_rate must be in [0,1], got {req.max_missing_rate}", "field": "max_missing_rate"})
    if req.license_requirement == "open" and req.access_tolerance == "account_ok":
        problems.append({"code": "REQUIREMENT_CONFLICT", "message": "license=open with access_tolerance=account_ok may be infeasible: many account sources have non-open terms", "field": "access_tolerance"})
    return problems
