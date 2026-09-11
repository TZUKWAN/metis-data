"""Format routing + parsers (P11-011..016, A20).

Routing uses content sniffing first (magic bytes/structure), extension only as a
hint. Labels preserved for DTA/SAV where possible; geo/science formats expose
schema + CRS/dimensions metadata; unsupported formats raise, never crash.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.errors import MetisError
from app.core.logging import get_logger

log = get_logger("formats")


class ParsedTable:
    """Lazy wrapper: profile/preview work chunked; full load is explicit."""

    def __init__(self, path: Path, fmt: str, reader, *, label: str | None = None, meta: dict | None = None) -> None:
        self.path = path
        self.fmt = fmt
        self._reader = reader  # callable -> pandas.DataFrame
        self.label = label
        self.meta = meta or {}
        self._df: pd.DataFrame | None = None

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._df = self._reader()
        return self._df

    def head(self, n: int = 20) -> pd.DataFrame:
        return self.df.head(n)

    @property
    def row_count(self) -> int:
        return len(self.df)

    @property
    def column_count(self) -> int:
        return self.df.shape[1]

    @property
    def columns(self) -> list[str]:
        return [str(c) for c in self.df.columns]

    def sheets(self) -> list[str]:
        return self.meta.get("sheets", [self.label or ""])


def sniff_format(path: Path) -> str:
    """Content-first format detection (A20: 不只根据扩展名盲判)."""
    with path.open("rb") as f:
        head = f.read(8192)
    if head.startswith(b"PAR1"):
        return "PARQUET"
    if head[:2] == b"PK":
        return "XLSX_OR_ZIP"
    if head[:8] == b"\x89HDF\r\n\x1a\n":
        return "NETCDF"
    if head.startswith(b"SQLite format 3"):
        return "SQLITE"
    if head[:4] in (b"RIFF",) or head[:80].lstrip().startswith((b"<?xml", b"<html", b"<HTML", b"<!DOCTYPE", b"<!doctype")):
        if b"<html" in head.lower() or b"<!doctype" in head.lower():
            return "HTML"
        return "XML"
    if head[:1] in (b"\x1f\x8b",):
        return "GZ"
    if head[:4] == b"RUSA" or head[:80].find(b"HEADER RECORD") >= 0:
        return "SAS_XPORT"
    if head[:4] in (b"\x05\x00",) or head[:1] == b"\x05" and b"STATA" in head[:120]:
        return "DTA"
    if head[:4] == b"$FL2":
        return "SAV"
    if head.lstrip().startswith(b"<stata_dta>"):
        return "DTA"
    # DTA 113/114/115: first byte 0x70/0x71/0x72 + version byte 1..3
    if head[:1] in (b"p", b"q", b"r") and 1 <= head[1] <= 3 and head[2] == 1:
        return "DTA"
    # text-ish: JSON vs JSONL vs delimiter tables
    text = head.decode("utf-8", errors="ignore").lstrip()
    if text.startswith(("[", "{")):
        if '"FeatureCollection"' in text or '"features"' in text[:2000]:
            return "GEOJSON"
        if path.stat().st_size < 5 * 1024 * 1024:
            try:
                json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                return "JSON"
            except json.JSONDecodeError:
                pass
        lines = [l for l in text.splitlines() if l.strip()]
        if len(lines) >= 2 and lines[-1].lstrip().startswith(("}", "]")) is False:
            return "JSONL"
        if path.stat().st_size > 8192:
            return "JSONL"  # multi-record stream truncated at 8KB
        return "JSON"
    if "\t" in text.splitlines()[0] if text else False:
        return "TSV"
    if "," in text.splitlines()[0] if text else False:
        return "CSV"
    return "TXT"


def _raise_unsupported(fmt: str) -> None:
    raise MetisError("PARSE_UNSUPPORTED_FORMAT", f"no parser for format {fmt}")



def _ascii_safe(path: Path) -> Path:
    """HDF5/netCDF4 on Windows cannot open non-ASCII paths; copy to ASCII temp when needed."""
    try:
        str(path).encode("ascii")
        return path
    except UnicodeEncodeError:
        import shutil
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        tmp = tmp_dir / ("copy_" + path.name)
        shutil.copy2(path, tmp)
        # sidecar files (e.g. .dbf/.shx/.prj for shapefiles) must travel together
        for sibling in path.parent.glob(path.stem + ".*"):
            shutil.copy2(sibling, tmp_dir / ("copy_" + sibling.name))
        return tmp

def parse_table(path: Path) -> ParsedTable:
    """Parse any supported tabular/scientific file into a ParsedTable."""
    if not path.exists():
        raise MetisError("NOT_FOUND", f"file not found: {path}")
    fmt = sniff_format(path)
    suffix = path.suffix.lower().lstrip(".")
    hints = {"csv": "CSV", "tsv": "TSV", "txt": "TXT", "json": "JSON", "jsonl": "JSONL", "parquet": "PARQUET",
             "xlsx": "XLSX", "xls": "XLS", "dta": "DTA", "sav": "SAV", "xpt": "SAS_XPORT",
             "geojson": "GEOJSON", "nc": "NETCDF", "db": "SQLITE", "sqlite": "SQLITE", "html": "HTML", "xml": "XML"}
    hint = hints.get(suffix)
    if fmt == "XLSX_OR_ZIP":
        fmt = hint if hint in ("XLSX", "XLS") else "ZIP"

    if suffix == "shp":  # shapefile sidecar set; route by component before text fallbacks
        def read_shp():
            import shapefile

            sf = shapefile.Reader(str(_ascii_safe(path)).rsplit(".", 1)[0])
            fields = [f[0] for f in sf.fields[1:]]
            rows = []
            for sr in sf.iterShapeRecords():
                row = dict(zip(fields, sr.record))
                row["_shape_type"] = sr.shape.shapeType
                rows.append(row)
            return pd.DataFrame(rows)

        import shapefile as _shpmod

        sf = _shpmod.Reader(str(_ascii_safe(path)).rsplit(".", 1)[0])
        shp_fields = [f[0] for f in sf.fields[1:]]
        n = len(sf.shapes())
        sf.close()
        return ParsedTable(path, "SHP", read_shp, meta={"shape_type": "shapefile", "fields": shp_fields, "features": n})

    if fmt in ("ZIP", "GZ"):
        import gzip
        import shutil
        import tempfile

        from app.downloads.service import MANAGER  # safe-extraction policy reuse

        tmp_root = Path(tempfile.mkdtemp(prefix="metis_zip_"))

        def read_archive():
            if fmt == "GZ":
                inner_name = path.stem if path.suffix.lower() == ".gz" else path.name + ".out"
                inner = tmp_root / inner_name
                with gzip.open(path, "rb") as src, inner.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                return parse_table(inner).df
            inner_dir = tmp_root / "x"
            members = MANAGER.safe_extract(path, inner_dir)
            import zipfile as _zf

            with _zf.ZipFile(path) as _zz:
                sizes = {i.filename: i.file_size for i in _zz.infolist()}
            tab = [m for m in members if m.suffix.lower() in (".csv", ".tsv", ".json", ".jsonl", ".parquet", ".xlsx", ".txt", ".dta", ".sav")]
            if not tab:
                raise MetisError("PARSE_FAILED", "archive contains no tabular data file")
            # main data file = largest non-"Metadata*" member (provider bundles ship side metadata)
            tab.sort(key=lambda m: (str(m.name).lower().startswith("metadata"), -sizes.get(m.name, 0)))
            main = tab[0]
            return parse_table(main).df

        members_preview: list[str] = []
        if fmt == "ZIP":
            import zipfile as _zf

            with _zf.ZipFile(path) as _z:
                members_preview = _z.namelist()[:20]
        return ParsedTable(path, "ZIP" if fmt == "ZIP" else "GZ", read_archive, meta={"members": members_preview})

    if fmt in ("CSV",):
        return ParsedTable(path, "CSV", lambda: _read_csv_flexible(path))
    if fmt == "TSV":
        return ParsedTable(path, "TSV", lambda: pd.read_csv(path, sep="\t"))
    if fmt == "TXT":
        return ParsedTable(path, "TXT", lambda: pd.read_csv(path, sep=None, engine="python"))
    if fmt == "JSON":
        return ParsedTable(path, "JSON", lambda: pd.json_normalize(_load_json(path)))
    if fmt == "JSONL":
        return ParsedTable(path, "JSONL", lambda: pd.json_normalize([json.loads(l) for l in path.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]))
    if fmt == "PARQUET":
        return ParsedTable(path, "PARQUET", lambda: pd.read_parquet(path))
    if fmt in ("XLSX", "XLS"):
        xls = pd.ExcelFile(path, engine="openpyxl" if fmt == "XLSX" or suffix == "xlsx" else "xlrd")
        sheets = xls.sheet_names
        return ParsedTable(path, "XLSX" if suffix == "xlsx" else "XLS", lambda: pd.read_excel(path, sheet_name=0), meta={"sheets": sheets, "sheet_count": len(sheets)})
    if fmt == "DTA":
        def read_dta():
            import pyreadstat

            df, meta = pyreadstat.read_dta(str(path))
            df.attrs["variable_labels"] = meta.column_names_to_labels
            df.attrs["value_labels"] = meta.variable_value_labels
            return df

        return ParsedTable(path, "DTA", read_dta)
    if fmt == "SAV":
        def read_sav():
            import pyreadstat

            df, meta = pyreadstat.read_sav(str(path))
            df.attrs["variable_labels"] = meta.column_names_to_labels
            df.attrs["value_labels"] = meta.variable_value_labels
            return df

        return ParsedTable(path, "SAV", read_sav)
    if fmt == "SAS_XPORT":
        def read_xpt():
            import pyreadstat

            df, meta = pyreadstat.read_xport(str(path))
            df.attrs["variable_labels"] = meta.column_names_to_labels
            return df

        return ParsedTable(path, "SAS_XPORT", read_xpt)
    if fmt == "GEOJSON":
        def read_geojson():
            data = _load_json(path)
            feats = data.get("features", []) if isinstance(data, dict) else []
            rows = []
            for f in feats:
                row = dict(f.get("properties", {}))
                row["_geometry_type"] = (f.get("geometry") or {}).get("type")
                row["_geometry_coords"] = json.dumps((f.get("geometry") or {}).get("coordinates"))[:2000]
                rows.append(row)
            return pd.DataFrame(rows)

        data = _load_json(path)
        crs = None
        if isinstance(data, dict):
            crs = (data.get("crs") or {}).get("properties", {}).get("name") if isinstance(data.get("crs"), dict) else None
        return ParsedTable(path, "GEOJSON", read_geojson, meta={"crs": crs or "CRS84", "geometry_types": sorted({(f.get("geometry") or {}).get("type") for f in data.get("features", []) if isinstance(data, dict)})})
    if suffix == "shp":
        def read_shp():
            import shapefile

            sf = shapefile.Reader(str(path))
            fields = [f[0] for f in sf.fields[1:]]
            rows = []
            for sr in sf.iterShapeRecords():
                row = dict(zip(fields, sr.record))
                row["_shape_type"] = sr.shape.shapeType
                rows.append(row)
            return pd.DataFrame(rows)

        return ParsedTable(path, "SHP", read_shp, meta={"shape_type": "shapefile"})
    if fmt == "NETCDF":
        def read_nc():
            from netCDF4 import Dataset

            ds = Dataset(str(_ascii_safe(path)))
            meta = {
                "dimensions": {k: len(v) for k, v in ds.dimensions.items()},
                "variables": {k: (str(v.dtype), str(getattr(v, "units", ""))) for k, v in ds.variables.items()},
            }
            ds.close()
            return pd.DataFrame([{"dimension": k, "size": v} for k, v in meta["dimensions"].items()])

        from netCDF4 import Dataset

        ds = Dataset(str(_ascii_safe(path)))
        meta = {
            "dimensions": {k: len(v) for k, v in ds.dimensions.items()},
            "variables": {k: {"dtype": str(v.dtype), "units": str(getattr(v, "units", "")), "long_name": str(getattr(v, "long_name", ""))} for k, v in ds.variables.items()},
        }
        ds.close()
        return ParsedTable(path, "NETCDF", read_nc, meta=meta)
    if fmt == "SQLITE":
        def read_sqlite():
            con = sqlite3.connect(str(path))
            try:
                tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                if not tables:
                    return pd.DataFrame()
                return pd.read_sql_query(f'SELECT * FROM "{tables[0]}"', con)
            finally:
                con.close()

        con = sqlite3.connect(str(path))
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        con.close()
        return ParsedTable(path, "SQLITE", read_sqlite, meta={"tables": tables})
    if fmt == "HTML":
        tables = pd.read_html(path)
        if not tables:
            raise MetisError("PARSE_FAILED", "no HTML tables found")
        return ParsedTable(path, "HTML_TABLE", lambda: tables[0], meta={"sheet_count": len(tables)})
    if fmt in ("XML", "ZIP", "GZ"):
        _raise_unsupported(fmt)
    _raise_unsupported(fmt)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def _read_csv_flexible(path: Path) -> pd.DataFrame:
    """Encoding + separator tolerant CSV reader (GBK/中文, provider preamble rows etc)."""
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030", "latin-1"):
        try:
            sample = path.open("rb").read(65536)
            sample.decode(enc)
        except UnicodeDecodeError:
            continue
        except Exception:  # noqa: BLE001
            return pd.read_csv(path, encoding=enc)
        # some providers prepend metadata rows before the header; skip until a
        # header-looking line (>=3 commas and no trailing colon-only line)
        skip = 0
        try:
            with path.open("r", encoding=enc, errors="replace") as fh:
                for i, line in enumerate(fh):
                    if i >= 12:
                        break
                    if line.count(",") >= 3 or line.count("	") >= 1:
                        skip = i
                        break
                else:
                    skip = 0
            return pd.read_csv(path, encoding=enc, sep=None, engine="python", skiprows=skip)
        except Exception:  # noqa: BLE001
            return pd.read_csv(path, encoding=enc, sep=None, engine="python", on_bad_lines="skip")
    raise MetisError("PARSE_FAILED", "could not decode file with any supported encoding")
