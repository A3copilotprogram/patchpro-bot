# PatchPro Analysis Architecture

## Overview

PatchPro has a unified analysis pipeline that can be used in different contexts (commits, PRs, manual). The core logic is extracted into reusable functions to avoid duplication.

## Core Components

### 1. Common Analysis Pipeline

**Function:** `_run_analysis_pipeline(files, artifacts_path, with_llm, tools, context)`

This is the **core reusable function** that:
- Runs static analysis tools (ruff, semgrep)
- Normalizes and merges findings
- Optionally generates AI patches with LLM
- Returns status dict with results

**Used by:** All analysis commands

### 2. Analysis Commands

#### `analyze-commit` - Post-Commit Analysis
**Context:** Local development (post-commit git hook)
- Triggered by: `git commit` via post-commit hook
- Analyzes: Files in the last commit (`HEAD`)
- Mode: Async (background) by default
- LLM: Optional (`--with-llm`)
- Output: `.patchpro/` artifacts

**Usage:**
```bash
# Async mode (used by git hook)
patchpro analyze-commit --async --with-llm

# Sync mode
patchpro analyze-commit --commit HEAD
```

**Hook Integration:**
```bash
# Post-commit hook
nohup python -m patchpro_bot.cli analyze-commit --async --with-llm > /dev/null 2>&1 &
```

#### `analyze-pr` - Pull Request Analysis
**Context:** CI/CD pipelines (GitHub Actions, GitLab CI, etc.)
- Triggered by: CI/CD workflow on PR
- Analyzes: Files changed between base and head (`base...head`)
- Mode: Sync (blocking for CI)
- LLM: Enabled by default
- Output: `.patchpro/` artifacts + exit code

**Usage:**
```bash
# GitHub Actions
patchpro analyze-pr --base origin/main --head HEAD

# GitLab CI
patchpro analyze-pr --base origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME

# Don't fail build on findings
patchpro analyze-pr --no-exit-code
```

**CI Integration Example (GitHub Actions):**
```yaml
- name: Analyze PR with PatchPro
  run: |
    patchpro analyze-pr --base origin/${{ github.base_ref }} --head HEAD
  continue-on-error: true  # Optional: don't fail build
  
- name: Upload patches
  uses: actions/upload-artifact@v3
  with:
    name: patchpro-patches
    path: .patchpro/patch_*.diff
```

### 3. Interactive Commands

#### `pre-push-prompt` - Pre-Push Review
**Context:** Local development (pre-push git hook)
- Triggered by: `git push` via pre-push hook
- Shows: Findings from post-commit analysis
- Actions: fix (apply patches), push (ignore), cancel
- Output: Interactive terminal prompt

#### `check-status` - Status Check
**Context:** Local development (anytime)
- Shows: Current analysis status
- Output: Human-readable status

#### `review-findings` - Manual Review
**Context:** Local development (anytime)
- Shows: Findings table with optional amend
- Actions: amend (apply patches to last commit), manual, ignore

## Data Flow

### Local Development Flow

```
git commit
    ↓
[post-commit hook] → analyze-commit --async --with-llm
    ↓
[Background analysis]
    ├─ Run ruff/semgrep
    ├─ Normalize findings
    ├─ Generate patches (LLM)
    └─ Write status.json + findings.json
    
... developer continues working ...

git push
    ↓
[pre-push hook] → pre-push-prompt
    ↓
[Interactive prompt]
    ├─ Read status.json
    ├─ Show findings table
    ├─ Prompt: fix/push/cancel
    └─ Apply patches + amend (if fix chosen)
```

### CI/CD Flow

```
Pull Request opened/updated
    ↓
[CI workflow trigger]
    ↓
analyze-pr --base origin/main --head HEAD
    ↓
[Sync analysis]
    ├─ Get changed files (git diff)
    ├─ Run ruff/semgrep
    ├─ Normalize findings
    ├─ Generate patches (LLM)
    ├─ Write artifacts
    ├─ Display findings table
    └─ Exit with code (0=success, 1=critical issues)
    
[CI continues]
    ├─ Upload patches as artifacts
    ├─ Comment on PR (optional)
    └─ Pass/fail based on exit code
```

## File Structure

```
.patchpro/
├── status.json              # Current analysis status
├── findings.json            # Normalized findings
├── patch_combined_*.diff    # Combined patch file
├── patch_*.diff            # Individual patches
└── analysis/
    ├── ruff.json           # Raw ruff output
    ├── semgrep.json        # Raw semgrep output
    └── normalized_findings.json
```

## Status States

**status.json format:**
```json
{
  "status": "idle|running|completed|error",
  "context": "commit|pr|manual",
  "files": ["file1.py", "file2.py"],
  "findings_count": 10,
  "critical_count": 2,
  "patches_available": true,
  "started_at": "2025-10-04T10:00:00",
  "completed_at": "2025-10-04T10:01:30"
}
```

## Extension Points

### Adding New Analysis Contexts

To add a new analysis context (e.g., `analyze-branch`, `analyze-diff`):

1. Create a new command function
2. Get the list of files to analyze
3. Call `_run_analysis_pipeline()` with appropriate context
4. Handle the results appropriately

**Example:**
```python
@app.command()
def analyze_branch(
    branch: str = typer.Argument(...),
    with_llm: bool = typer.Option(True, "--with-llm"),
):
    """Analyze all files in a branch."""
    # Get files in branch
    files = _get_branch_files(branch)
    
    # Run common pipeline
    status = _run_analysis_pipeline(
        files=files,
        artifacts_path=Path(".patchpro"),
        with_llm=with_llm,
        context="branch"
    )
    
    # Display results
    _display_results(status)
```

### Adding New Tools

To add a new tool (e.g., `mypy`, `pylint`):

1. Create `_run_<tool>()` function in `cli.py`
2. Add tool to `tools` parameter in commands
3. Update `_run_analysis_pipeline()` to call the tool

## Best Practices

### For Local Development
- Use `--async` for post-commit to keep commits fast
- Use `--with-llm` to generate patches automatically
- Review findings with `patchpro review-findings` anytime

### For CI/CD
- Always use `analyze-pr` for PR analysis (not `analyze-commit`)
- Upload patches as artifacts for manual review
- Use `--no-exit-code` if you don't want to fail builds
- Consider adding PR comments with findings

### For Tool Configuration
- Specify tools explicitly: `--tools ruff semgrep`
- Use project configs (`.ruff.toml`, `.semgrep.yml`)
- Exclude patterns via config files

## Migration Guide

### From Old Commands

| Old Command | New Command | Notes |
|------------|-------------|-------|
| `analyze-staged` | `analyze-commit` | More accurate name |
| `analyze-staged --last-commit` | `analyze-commit` | Default behavior |
| `diff_analyze --staged` | `analyze-commit` | Use for commits |
| `diff_analyze --base origin/main` | `analyze-pr` | Use for PRs |
| Manual analysis | `analyze` | Still available |

### Updating Hooks

Update your git hooks to use the new commands:

```bash
# Old post-commit hook
python -m patchpro_bot.cli analyze-staged --async --with-llm --last-commit

# New post-commit hook
python -m patchpro_bot.cli analyze-commit --async --with-llm
```

## Performance Considerations

- **Post-commit (async)**: ~0.1s commit time + 10-30s background analysis
- **Pre-push (sync)**: Instant if analysis complete, 10-30s if still running
- **CI/PR (sync)**: 15-60s depending on changed files count
- **LLM patches**: +5-20s depending on findings count

## Security Considerations

- **API Keys**: Store in environment variables, never in code
- **Patches**: Review before applying, especially in CI
- **File Access**: Analysis only reads files, doesn't modify without confirmation
- **Network**: LLM calls require internet, tools are local

## Troubleshooting

### Analysis not running
```bash
# Check status
patchpro check-status

# Check if hooks are installed
cat .git/hooks/post-commit
```

### Patches not applying
```bash
# Check patch validity
git apply --check .patchpro/patch_combined_*.diff

# Manual apply
git apply .patchpro/patch_combined_*.diff
```

### CI failing unexpectedly
```bash
# Run locally to reproduce
patchpro analyze-pr --base origin/main --head HEAD

# Check artifacts
ls -la .patchpro/
```
