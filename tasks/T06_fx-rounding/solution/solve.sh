#!/usr/bin/env bash
set -euo pipefail
# Oracle-only artifacts are made available by Harbor at /solution.
cp /solution/service.py /app/service.py
python -m py_compile /app/service.py
