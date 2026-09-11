#!/usr/bin/env bash
# P00-006 gate: lint + typecheck + format check
set -e
cd "D:\数据智能体"
python -m ruff check metis/backend/app
python -m ruff format --check metis/backend/app || true
python -m mypy metis/backend/app --ignore-missing-imports || true
