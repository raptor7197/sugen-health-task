#!/usr/bin/env bash
set -euo pipefail
cd /home/krxsna/dev/SugenEngTest
mkdir -p scripts/diagnostics
for name in benchmark profile_run probe_slow probe_scale probe_stage; do
  if [ -f "tests/${name}.py" ]; then
    mv "tests/${name}.py" "scripts/diagnostics/${name}.py"
  fi
done
ls tests scripts/diagnostics