#!/bin/sh
# PatchPro-Bot: Full automation script for CI and local dev

set -e

case "$1" in
  test)
    echo "Running tests..."
    PYTHONPATH=src pytest tests
    ;;
  lint)
    echo "Running Ruff linter..."
    ruff src/patchpro_bot
    ;;
  semgrep)
    echo "Running Semgrep..."
    semgrep --config=semgrep.yml src/patchpro_bot
    ;;
  all|"")
    echo "Running all checks (lint, semgrep, test)..."
    ruff src/patchpro_bot
    semgrep --config=semgrep.yml src/patchpro_bot
    PYTHONPATH=src pytest tests
    ;;
  *)
    echo "Usage: $0 [test|lint|semgrep|all]"
    exit 1
    ;;
esac
