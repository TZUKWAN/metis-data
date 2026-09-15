# Methodology — Build build_5ad348661fdc4ee0a0db

Generated automatically from build provenance on 2026-09-15T20:41:03.137414+00:00. This document describes only operations that actually ran; no step is invented.

## 1. Data sources
- **ilostat** dataset `DF_UNE_3EAP_SEX_AGE_STU_RT` (Youth unemployment rate by sex, age and school attendance status)
  - URL: https://ilostat.ilo.org/data/
  - DOI: n/a | version: n/a
  - License: CC-BY-4.0
  - Downloaded: 2026-09-15T20:36:40.604856+00:00 via UNKNOWN
  - SHA256: `91bdd806ae9e1ced6576423acd0f17b97239fb417d0c8c47f45753ba116a9bea`

## 2. Variable selection and mapping
- input `op_253756d10ad442ce9246`: art_4d037289975a4aeabff0 columns kept as loaded
- input `op_53de538389e646bebeea`: art_4d037289975a4aeabff0 columns kept as loaded

## 3. Entity alignment
- columns processed: []; resolved 0 unique values; unresolved (left NULL, never guessed): []

## 4. Time alignment
- `op_2e16089196884ac1b1bc`: {"time_column": null}

## 5. Join

## 6. Missing data treatment
- method `none`; imputed cells 0 (0.0 of missing); all imputed cells flagged via `__imputed_*` columns

## 7. Derived variables

## 8. Quality checks
- [INFO] MISSING: column OBS_VALUE missing 6.4%
- [WARNING] MISSING_HIGH: column OBS_STATUS has 77% missing — remediation: consider a missing policy (documented) or drop the column
- [INFO] MISSING: column NOTE_SOURCE missing 0.6%
- [WARNING] MISSING_HIGH: column NOTE_INDICATOR has 91% missing — remediation: consider a missing policy (documented) or drop the column
- [WARNING] MISSING_HIGH: column NOTE_CLASSIF has 100% missing — remediation: consider a missing policy (documented) or drop the column
- [WARNING] MISSING_HIGH: column UPPER_BOUND has 100% missing — remediation: consider a missing policy (documented) or drop the column
- [WARNING] MISSING_HIGH: column LOWER_BOUND has 100% missing — remediation: consider a missing policy (documented) or drop the column
- [WARNING] CONSTANT_COLUMN: column DATAFLOW is constant — remediation: verify whether the constant is expected
- [WARNING] CONSTANT_COLUMN: column FREQ is constant — remediation: verify whether the constant is expected
- [WARNING] CONSTANT_COLUMN: column MEASURE is constant — remediation: verify whether the constant is expected
- [WARNING] CONSTANT_COLUMN: column UNIT_MEASURE_TYPE is constant — remediation: verify whether the constant is expected
- [WARNING] CONSTANT_COLUMN: column UNIT_MEASURE is constant — remediation: verify whether the constant is expected
- [WARNING] CONSTANT_COLUMN: column UNIT_MULT is constant — remediation: verify whether the constant is expected
- [WARNING] CONSTANT_COLUMN: column NOTE_CLASSIF is constant — remediation: verify whether the constant is expected
- [WARNING] CONSTANT_COLUMN: column DECIMALS is constant — remediation: verify whether the constant is expected
- [WARNING] CONSTANT_COLUMN: column UPPER_BOUND is constant — remediation: verify whether the constant is expected
- [WARNING] CONSTANT_COLUMN: column LOWER_BOUND is constant — remediation: verify whether the constant is expected

## 9. Warnings recorded during transformation
- none
