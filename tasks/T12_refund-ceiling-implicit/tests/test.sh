#!/usr/bin/env bash
set -uo pipefail
mkdir -p /logs/verifier
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTHONPATH=/app
cd /app || exit 2
if python -m pytest -q -p no:cacheprovider /tests/test_service.py > /logs/verifier/pytest.log 2>&1; then
  printf '1\n' > /logs/verifier/reward.txt
else
  printf '0\n' > /logs/verifier/reward.txt
fi
cat /logs/verifier/pytest.log
# Exit 0 even for a failed solution; the reward file carries task success/failure.
exit 0
