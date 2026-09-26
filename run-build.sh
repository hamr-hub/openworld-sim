#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p logs
: > logs/run.log
claude -p "$(cat TASK.md)" \
  --dangerously-skip-permissions \
  --max-turns 400 \
  --output-format json \
  > logs/run.log 2>&1
echo "CLAUDE_EXIT=$?" >> logs/run.log
