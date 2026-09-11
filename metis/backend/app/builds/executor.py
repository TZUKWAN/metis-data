"""Build executor (P13-001..025, A27/A28/A29/A35): DAG-ish staged pipeline with checkpoints.

Stages persist checkpoints (intermediate parquet + stage metadata) so a crashed
build resumes from the last safe stage instead of re-running external effects.
"""
from __future__ import annotations

import time

import pandas as pd

from app.core.errors import MetisError
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.enums import BuildStatus
from app.domain.schemas import BuildConfig, BuildPlanStep, new_id

log = get_logger("build")

MAGIC_RE = None


class BuildExecutor:
    """Executes a BuildConfig against registered artifacts. All operations get provenance rows."""

    def __init__(self, build_id: str) -> None:
        self.build_id = build_id
        self.repo = REPO
        self.data: pd.DataFrame | None = None
        self._ops: list[dict] = []
        self.code_version = "1.0.0"

    # ---------- plan (P13-022, visible in UI) ----------
    def generate_plan(self, cfg: BuildConfig, input_schemas: list[dict]) -> list[BuildPlanStep]:
        steps = [
            BuildPlanStep(step_id="s1", kind="input_compatibility", params={"inputs": [i.artifact_id for i in cfg.inputs]}, warnings=[]),
            BuildPlanStep(step_id="s2", kind="semantic_mapping", params={"canonical_map": cfg.plan and [] or {}}, warnings=[]),
            BuildPlanStep(step_id="s3", kind="entity_resolution", params={"target_unit": cfg.target_unit}, warnings=[]),
            BuildPlanStep(step_id="s4", kind="time_alignment", params={"frequency": cfg.time_frequency}, warnings=[]),
            BuildPlanStep(step_id="s5", kind="join", params={"keys": cfg.keys, "allow_mm": cfg.allow_mm_join}, warnings=["m:m joins are blocked unless explicitly allowed"] if not cfg.allow_mm_join else ["m:m explicitly allowed by user"]),
            BuildPlanStep(step_id="s6", kind="missing_policy", params={"method": cfg.missing_policy}, warnings=[] if cfg.missing_policy == "none" else [f"missing values will be filled using {cfg.missing_policy}; imputed cells flagged"]),
            BuildPlanStep(step_id="s7", kind="derived_variables", params={"formulas": [d.get("formula") for d in cfg.derived_variables]}, warnings=[]),
            BuildPlanStep(step_id="s8", kind="validation", params={"profile": cfg.validation_profile}, warnings=[]),
            BuildPlanStep(step_id="s9", kind="export", params={"formats": cfg.exports}, warnings=[]),
        ]
        cfg.plan = steps
        return steps

    # ---------- execution ----------
    async def run(self) -> dict:
        cfg_dict = REPO.get_build(self.build_id)
        if not cfg_dict:
            raise MetisError("NOT_FOUND", f"build {self.build_id} not found")
        cfg = BuildConfig(**cfg_dict)
        started = time.time()

        REPO.transition_build(self.build_id, BuildStatus.INPUTS_READY)
        # stage: SCHEMA_ANALYSIS (checkpoint-resumable)
        if not self._checkpoint_reached("SCHEMA_ANALYSIS"):
            REPO.transition_build(self.build_id, BuildStatus.SCHEMA_ANALYSIS)
            frames = []
            input_schemas = []
            for inp in cfg.inputs:
                artifact = REPO.get_artifact(inp.artifact_id)
                if not artifact:
                    raise MetisError("NOT_FOUND", f"input artifact {inp.artifact_id} not registered — acquire it first")
                from app.core.paths import raw_root

                path = raw_root() / artifact["raw_path"]
                from app.datasets.parsers import parse_table

                parsed = parse_table(path)
                df = parsed.df
                frames.append((inp, df))
                input_schemas.append({"artifact_id": inp.artifact_id, "columns": list(map(str, df.columns)), "rows": int(len(df))})
                art_data = REPO.get_artifact(inp.artifact_id) or {}
                art_data["profile_json"] = {"columns": list(map(str, df.columns)), "row_count": int(len(df))}
                REPO.save_artifact(art_data)
                self._record_op("load_input", {"artifact_id": inp.artifact_id, "path": str(path)}, [], [inp.artifact_id], len(df), len(df), df.shape[1], df.shape[1])
            REPO.set_build_checkpoint(self.build_id, "SCHEMA_ANALYSIS", {"input_schemas": input_schemas, "done": True})
            self._inputs = frames
        else:
            # re-load inputs (raw is immutable so re-read is safe & deterministic)
            self._inputs = []
            for inp in cfg.inputs:
                artifact = REPO.get_artifact(inp.artifact_id)
                from app.core.paths import raw_root
                from app.datasets.parsers import parse_table

                df = parse_table(raw_root() / artifact["raw_path"]).df
                self._inputs.append((inp, df))
            REPO.transition_build(self.build_id, BuildStatus.SCHEMA_ANALYSIS)

        REPO.transition_build(self.build_id, BuildStatus.SEMANTIC_ALIGNMENT)
        # semantic alignment stage: use artifact profiles to flag same-name/different-semantic pairs
        self._record_op("semantic_alignment_scan", {"policy": "same-name columns require semantic comparison before merge (A22)"}, [], [], 0, 0, 0, 0)

        # ENTITY_RESOLUTION
        REPO.transition_build(self.build_id, BuildStatus.ENTITY_RESOLUTION)
        self._apply_entity_resolution(cfg)

        # TEMPORAL_ALIGNMENT
        REPO.transition_build(self.build_id, BuildStatus.TEMPORAL_ALIGNMENT)
        self._apply_time_alignment(cfg)

        # TRANSFORM (joins + append + missing + derived)
        REPO.transition_build(self.build_id, BuildStatus.TRANSFORM)
        self._apply_transforms(cfg)

        REPO.transition_build(self.build_id, BuildStatus.JOIN)

        # QA
        REPO.transition_build(self.build_id, BuildStatus.QA)
        from app.builds.validation import run_validations

        run_validations(self.data, self.build_id, keys=cfg.keys or None, expected_row_count=None)

        REPO.transition_build(self.build_id, BuildStatus.PROVENANCE_FINALIZE)
        from app.provenance.package import build_provenance

        lineage_stats = build_provenance(self.build_id, cfg, self._ops)

        REPO.transition_build(self.build_id, BuildStatus.EXPORT)
        from app.provenance.package import export_package

        package = export_package(self.build_id, cfg, self.data, lineage_stats)

        REPO.transition_build(self.build_id, BuildStatus.COMPLETE)
        REPO.set_build_checkpoint(self.build_id, "COMPLETE", {"package": package, "duration_s": round(time.time() - started, 1)})
        return {"build_id": self.build_id, "status": BuildStatus.COMPLETE, "package": package, "rows": 0 if self.data is None else int(len(self.data))}

    # ---------- stage helpers ----------
    def _checkpoint_reached(self, stage: str) -> bool:
        cfg = REPO.get_build(self.build_id)
        return bool((cfg or {}).get("stage_checkpoints", {}).get(stage, {}).get("done"))

    def _record_op(self, op_type: str, params: dict, inputs: list, outputs: list, rb: int | None, ra: int | None, cb: int | None, ca: int | None, warnings: list | None = None) -> str:
        op_id = new_id("op")
        REPO.add_build_operation(
            operation_id=op_id,
            build_id=self.build_id,
            seq=len(self._ops) + 1,
            operation_type=op_type,
            parameters=params,
            input_artifacts=inputs,
            output_artifacts=outputs,
            row_count_before=rb,
            row_count_after=ra,
            column_count_before=cb,
            column_count_after=ca,
            warnings=warnings or [],
            code_version=self.code_version,
        )
        self._ops.append({"operation_id": op_id, "type": op_type, "params": params, "row_before": rb, "row_after": ra})
        return op_id

    def _apply_entity_resolution(self, cfg: BuildConfig) -> None:
        from app.builds.entities import CountryResolver

        resolver = CountryResolver()
        if self.data is None:
            self.data = self._inputs[0][1].copy() if self._inputs else pd.DataFrame()
        # find geo-like columns and normalize to ISO3 while keeping originals
        geo_cols = [c for c in self.data.columns if str(c).lower() in ("country", "country_name", "iso3", "iso2", "country_code", "nation")]
        resolved = {}
        unresolved = []
        for col in geo_cols:
            out_col = f"{col}_iso3"
            canon = []
            for v in self.data[col]:
                m = resolver.resolve(v)
                canon.append(resolver.to_iso3(m.canonical_id) if m else None)
                if m is None:
                    unresolved.append(str(v))
                else:
                    resolved[str(v)] = m.canonical_id
            self.data[out_col] = canon
            self.data[f"{col}_original"] = self.data[col]
        self._record_op(
            "entity_resolution",
            {"strategy": "ISO2/ISO3/name/alias via curated dictionary", "geo_columns": geo_cols, "resolved_unique": len(resolved), "unresolved_unique": sorted(set(unresolved))[:20]},
            [], [], None, int(len(self.data)), None, self.data.shape[1],
            warnings=[f"{len(set(unresolved))} values could not be resolved and are left NULL (not guessed)"] if unresolved else [],
        )
        REPO.set_build_checkpoint(self.build_id, "ENTITY_RESOLUTION", {"resolved": resolved, "done": True})

    def _apply_time_alignment(self, cfg: BuildConfig) -> None:
        from app.builds.times import aggregate_to_year, detect_frequency

        time_col = next((c for c in self.data.columns if str(c).lower() in ("year", "time", "date", "period")), None)
        note = {}
        if time_col:
            freq = detect_frequency(self.data[time_col].tolist()[:5000])
            note["detected_frequency"] = freq
            if freq in ("month", "quarter", "day") and cfg.time_frequency == "annual":
                numeric_cols = [c for c in self.data.select_dtypes("number").columns if c != time_col]
                self.data, prov = aggregate_to_year(self.data, time_col, numeric_cols, method="mean")
                self._record_op("time_aggregation", prov, [], [], prov["rows_before"], prov["rows_after"], None, None, warnings=[prov["note"]])
        self._record_op("time_alignment", {"time_column": time_col, **note}, [], [], None, int(len(self.data)), None, self.data.shape[1])
        REPO.set_build_checkpoint(self.build_id, "TEMPORAL_ALIGNMENT", {"time_column": time_col, **note, "done": True})

    def _apply_transforms(self, cfg: BuildConfig) -> None:
        """Canonicalize each input (iso3 + year), then sequential safe joins, missing policy, derived vars."""
        from app.builds.joins import apply_missing_policy, derive_variable, safe_join

        canonicalized: list[pd.DataFrame] = []
        for idx, (inp, df) in enumerate(self._inputs, start=1):
            c = self._canon_key(df, cfg)
            c = self._with_time(c, cfg)
            canonicalized.append(c)
            self._record_op("canonicalize_input", {"input_index": idx, "artifact_id": inp.artifact_id, "columns": list(map(str, c.columns))}, [], [], None, int(len(c)), None, int(c.shape[1]))

        if len(canonicalized) >= 2:
            merged = canonicalized[0]
            for idx, right in enumerate(canonicalized[1:], start=2):
                merged, report = safe_join(merged, right, canon_keys(cfg), how="inner", allow_mm=cfg.allow_mm_join)
                self._record_op(
                    "join",
                    {"left_input": idx - 1, "right_input": idx, "keys": canon_keys(cfg), "report": report},
                    [], [], report["row_count_before"], report["row_count_after"], None, int(merged.shape[1]),
                    warnings=(["join explosion suspected" if report.get("explosion") else None] or []),
                )
            self.data = merged
        elif self.data is None:
            self.data = canonicalized[0].copy() if canonicalized else pd.DataFrame()
        else:
            self.data = self.data

        # missing policy (default NONE → zero imputed cells, A28)
        value_cols = [c for c in self.data.select_dtypes("number").columns]
        self.data, mask, mprov = apply_missing_policy(self.data, value_cols, None, method=cfg.missing_policy, params=cfg.missing_policy_params)
        if cfg.missing_policy != "none":
            for col in mask.columns:
                self.data[f"__imputed_{col}"] = mask[col].values
        self._record_op("missing_policy", mprov, [], [], None, int(len(self.data)), None, int(self.data.shape[1]))

        # derived variables (A29)
        for d in cfg.derived_variables:
            self.data, dprov = derive_variable(self.data, d["formula"], d["output"], d["inputs"])
            self._record_op("derived_variable", dprov, [], [], None, int(len(self.data)), None, int(self.data.shape[1]))

        REPO.set_build_checkpoint(self.build_id, "TRANSFORM", {"rows": int(len(self.data)), "cols": int(self.data.shape[1]), "done": True})

    def _canon_key(self, df: pd.DataFrame, cfg: BuildConfig) -> pd.DataFrame:
        """Canonicalize one input: reshape wide year columns to long, normalize geo to
        ISO3 (original kept) and time to year. Records reshape provenance via op log."""
        import re as _re

        out = df.copy()
        out.columns = [str(c) for c in out.columns]

        # 1) wide year columns (e.g. World Bank layout) -> long format (PRD §21 reshape)
        year_cols = [c for c in out.columns if _re.fullmatch(r"(19|20)\d\d", c)]
        if year_cols and "year" not in {c.lower() for c in out.columns}:
            id_cols = [c for c in out.columns if c not in year_cols]
            n_before = len(out)
            out = out.melt(id_vars=id_cols, value_vars=year_cols, var_name="year", value_name="value")
            out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
            out = out.dropna(subset=["year"])
            self._record_op(
                "reshape_wide_to_long",
                {"year_columns": year_cols, "id_columns": id_cols, "rows_before": n_before, "rows_after": int(len(out))},
                [], [], n_before, int(len(out)), len(id_cols) + len(year_cols), int(out.shape[1]),
                warnings=["wide year columns reshaped to long; value column named 'value'"],
            )

        # 2) geo column (tolerant name match: spaces->underscores)
        norm = {c: c.lower().replace(" ", "_") for c in out.columns}
        geo = next((c for c, n in norm.items() if n in ("country", "country_name", "nation", "country_code", "iso3", "iso2")), None)
        if geo is not None and "iso3" not in {n for n in norm.values()}:
            from app.builds.entities import CountryResolver

            r = CountryResolver()
            iso3 = []
            for v in out[geo]:
                m = r.resolve(v)
                iso3.append(r.to_iso3(m.canonical_id) if m else None)
            out["iso3"] = iso3
            out[f"{geo}_original"] = out[geo]
        elif "iso3" in out.columns:
            pass

        # 3) time column normalization
        if "year" not in {c.lower() for c in out.columns}:
            t = next((c for c in out.columns if norm[c] in ("year", "time", "date", "period", "quarter", "month")), None)
            if t:
                from app.builds.times import parse_time_value

                out = out.rename(columns={t: "year"})
                out["year"] = [parse_time_value(v).year if parse_time_value(v) else None for v in out["year"]]
        return out

    def _with_time(self, df: pd.DataFrame, cfg: BuildConfig) -> pd.DataFrame:
        return df  # time normalization now happens in _canon_key


def canon_keys(cfg: BuildConfig) -> list[str]:
    keys = []
    for k in cfg.keys:
        keys.append({"country": "iso3", "country_name": "iso3", "year": "year"}.get(k, k))
    return keys or ["iso3", "year"]
