# PatchPro-Bot Automation & Developer Guide


## Automation Scripts

- **Makefile**: Run `make test`, `make lint`, `make semgrep`, or `make all` for full checks.
- **PowerShell**: Run `./dev.ps1 [test|lint|semgrep|all]` on Windows.
- **Shell**: Run `./dev.sh [test|lint|semgrep|all]` on Linux/macOS.

All scripts:

- Lint with Ruff
- Run Semgrep static analysis
- Run tests with correct `PYTHONPATH`


## Pre-commit Hook

- Copy `.pre-commit-hook` to `.git/hooks/pre-commit` and make it executable:

  ```sh
  cp .pre-commit-hook .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit
  ```

- This blocks commits if Ruff or Semgrep fail.

## CI/CD

- The GitHub Actions workflow runs Ruff, Semgrep, and tests with `PYTHONPATH` set for correct imports.
- Artifacts and reports are uploaded for review.

## Best Practices

- All importable code in `src/patchpro_bot/`.
- All tests in `tests/`, importing from `patchpro_bot`.
- Always set `PYTHONPATH` to `src` (or `patchpro-bot/src` from workspace root) for tests and scripts.
- Use automation scripts for consistency.

## How to Contribute

1. Run `make all` or `./dev.ps1 all` or `./dev.sh all` before pushing.
2. Ensure pre-commit hook is enabled.
3. Push your branch and open a PR.
4. CI will validate your changes automatically.

---

For more, see `TESTING.md`, `PRECOMMIT.md`, or ask GitHub Copilot.
