# PatchPro Bot

PatchPro is a CI code-repair assistant that automatically analyzes pull requests, suggests minimal code diffs, and posts actionable feedback as sticky comments.

## Features

- **Automated PR Review:** On every pull request, PatchPro runs static analysis (Ruff, Semgrep), merges findings, and generates a markdown summary.
- **GitHub Actions Workflow:** The workflow (`.github/workflows/patchpro.yml`) orchestrates analysis, agent execution, and comment posting.
- **Findings Merger:** The script `scripts/merge_findings.py` combines Ruff and Semgrep results into a normalized JSON format for PatchPro agent input.
- **Testing Suite:** Comprehensive unit tests using pytest to validate core functionality, including hello world examples and CI run simulations.

## How It Works

1. **Pull Request Trigger:** The workflow runs on every PR.
2. **Static Analysis:** Ruff and Semgrep scan the codebase and export findings as JSON.
3. **Findings Merge:** `merge_findings.py` merges and deduplicates findings.
4. **PatchPro Agent:** The agent processes findings and generates a markdown comment (`patchpro.md`).
5. **Sticky PR Comment:** The workflow posts the comment to the PR using [marocchino/sticky-pull-request-comment](https://github.com/marocchino/sticky-pull-request-comment).
6. **Local Testing and Validation:** Run the full test suite with pytest to ensure components work correctly before deployment.

## Project Structure

- `src/`: Core source code (e.g., `patchpro_bot/run_ci.py` for CI logic).
- `tests/`: Unit tests (e.g., `test_hello.py`, `test_run_ci.py`).
- `scripts/`: Utility scripts (e.g., `merge_findings.py`).
- `.github/workflows/`: GitHub Actions workflows.
- `docs/`: Documentation (e.g., `requirements.md`).
- `pytest.ini`: Pytest configuration for test discovery.

## Usage

### GitHub Actions

See `.github/workflows/patchpro.yml` for the full workflow definition.

### Merging Findings Locally

```bash
python scripts/merge_findings.py ruff-findings.json semgrep-findings.json findings.json
```

## Contributing

- Edit the workflow or scripts to improve automation, normalization, or feedback quality.
- See `docs/requirements.md` for pod-level requirements and development guidance.

---

For more details, see the [requirements document](docs/requirements.md).
