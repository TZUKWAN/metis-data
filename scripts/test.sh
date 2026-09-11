#!/usr/bin/env bash
set -e
cd "D:\数据智能体"
python -m pytest metis/backend/tests -q "$@"
