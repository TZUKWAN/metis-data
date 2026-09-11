"""Shared helpers for provider adapters."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.domain.schemas import AcquisitionSource, DatasetCandidate


def normalize_doi(doi: str | None) -> str | None:
    """Normalize to https://doi.org/<sx form> (A3: DOI 规范化)."""
    if not doi:
        return None
    d = doi.strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    if not d.lower().startswith("10."):
        return None
    return f"https://doi.org/{d}"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def mk_candidate(
    provider_id: str,
    title: str,
    source_url: str,
    *,
    description: str = "",
    publisher: str = "",
    authors: list[str] | None = None,
    doi: str | None = None,
    version: str | None = None,
    license: str = "UNKNOWN",
    access_mode: str = "UNKNOWN",
    requires_login: bool = False,
    restricted: bool = False,
    time_start: str | None = None,
    time_end: str | None = None,
    geography: list[str] | None = None,
    unit_of_analysis: str = "UNKNOWN",
    variable_hints: list[str] | None = None,
    source_ref: str = "",
    direct_file_url: str | None = None,
    file_format: str | None = None,
) -> DatasetCandidate:
    src = AcquisitionSource(
        provider_id=provider_id,
        source_url=source_url,
        source_ref=source_ref,
        direct_file_url=direct_file_url,
        file_format=file_format,
    )
    return DatasetCandidate(
        provider_id=provider_id,
        title=title,
        description=description or "UNKNOWN",
        publisher=publisher or "UNKNOWN",
        authors=authors or [],
        doi=normalize_doi(doi),
        version=version,
        license=license or "UNKNOWN",
        access_mode=access_mode,
        requires_login=requires_login,
        restricted=restricted,
        geography=geography or [],
        unit_of_analysis=unit_of_analysis,
        variable_hints=variable_hints or [],
        files=[src],
        sources=[src],
        time_coverage={"start": time_start, "end": time_end, "note": ""},  # type: ignore[arg-type]
    )


def looks_like_html(content: bytes) -> bool:
    head = content[:4096].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<html" in head or b"<!doctype html" in head


def licenses_from_ckan(license_id: str | None, license_title: str | None = None) -> str:
    lid = (license_id or license_title or "UNKNOWN").lower()
    mapping = {
        "cc-by-4.0": "CC-BY-4.0",
        "cc-by-3.0": "CC-BY-3.0",
        "cc-by": "CC-BY-4.0",
        "cc0-1.0": "CC0-1.0",
        "cc-zero": "CC0-1.0",
        "odc-by": "ODbL",
        "odc-pddl": "CC0-1.0",
        "odc-odbl": "ODbL",
        "other-open": "OPEN(unknown type)",
        "uk-ogl": "OGL-UK",
        "notspecified": "UNKNOWN",
        "": "UNKNOWN",
    }
    return mapping.get(lid, (license_title or license_id or "UNKNOWN").upper() if (license_title or license_id) else "UNKNOWN")


def guess_format_from_url(url: str) -> str | None:
    u = url.lower().split("?")[0]
    for ext, fmt in [
        (".csv", "CSV"), (".tsv", "TSV"), (".xlsx", "XLSX"), (".xls", "XLS"), (".json", "JSON"),
        (".jsonl", "JSONL"), (".zip", "ZIP"), (".gz", "GZ"), (".tar", "TAR"), (".parquet", "PARQUET"),
        (".dta", "DTA"), (".sav", "SAV"), (".nc", "NETCDF"), (".geojson", "GEOJSON"), (".shp", "SHP"),
        (".rdf", "RDF"), (".xml", "XML"), (".txt", "TXT"), (".pdf", "PDF"),
    ]:
        if u.endswith(ext):
            return fmt
    return None


def safe_get(d: dict | Any, *path: str, default: Any = None) -> Any:
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
        if cur is None:
            return default
    return cur


SMALL_PAYLOAD_CAP = 32 * 1024 * 1024  # 32MB


def write_small_payload(path, content: bytes, *, max_bytes: int = SMALL_PAYLOAD_CAP) -> None:
    """Bounded write for SMALL API payloads (JSON/CSV metadata responses).

    Large dataset downloads MUST go through DownloadManager streaming — never
    through this helper (P06-005).
    """
    if len(content) > max_bytes:
        from app.core.errors import MetisError

        raise MetisError("DOWNLOAD_TOO_LARGE", f"payload {len(content)} bytes exceeds small-payload cap {max_bytes}; use DownloadManager streaming")
    Path(path).write_bytes(content)
