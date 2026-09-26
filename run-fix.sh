#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p logs
: > logs/fix.log
claude -p "$(cat FIX.md)" \
  --dangerously-skip-permissions \
  --max-turns 400 \
  --output-format json \
  > logs/fix.log 2>&1
echo "CLAUDE_EXIT=$?" >> logs/fix.log
