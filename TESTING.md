# PatchPro-Bot Test & Development Workflow

This project uses a modern Python package structure for robust development and CI. Follow these guidelines for running tests and development:

## Directory Structure

- Source code: `patchpro-bot/src/patchpro_bot/`
- Tests: `patchpro-bot/tests/`
- Entry point for testable modules: `patchpro-bot/src/patchpro_bot/`

## Running Tests Locally

1. **From the `patchpro-bot` directory:**
   ```powershell
   $env:PYTHONPATH='src'; pytest tests
   ```
   This ensures the `patchpro_bot` package is importable by tests.

2. **From the workspace root:**
   ```powershell
   $env:PYTHONPATH='patchpro-bot/src'; pytest patchpro-bot/tests
   ```

## Continuous Integration (CI)

- The GitHub Actions workflow should set `PYTHONPATH` to `patchpro-bot/src` before running tests.
- Example CI step:
  ```yaml
  - name: Run tests
    run: |
      export PYTHONPATH=patchpro-bot/src
      pytest patchpro-bot/tests
  ```

## Linting & Static Analysis

- Run Ruff and Semgrep from the workspace root:
  ```powershell
  ruff patchpro-bot/src/patchpro_bot
  semgrep --config=patchpro-bot/semgrep.yml patchpro-bot/src/patchpro_bot
  ```

## Best Practices

- Place all importable code in `src/patchpro_bot/`.
- Keep tests in `patchpro-bot/tests/` and import from `patchpro_bot`.
- Always set `PYTHONPATH` to the `src` directory for both local and CI test runs.
- Use relative imports only within the package, never in tests.

---

For more details, see the README or ask GitHub Copilot for help.
