# PatchPro Local Developer Guide

PatchPro can be used locally by developers to analyze and fix code issues before committing or pushing changes.

## Installation

```bash
# Install PatchPro locally
pip install git+https://github.com/A3copilotprogram/patchpro-bot.git@agent-dev

# Install analysis tools
pip install ruff semgrep
```

## Local Usage Patterns

### 1. **Pre-Commit Analysis**
Analyze changes before committing:

```bash
# Analyze staged changes
git diff --cached --name-only | grep '\.py$' | xargs python -m patchpro_bot.cli run-ci --base-dir .

# Or analyze specific files
python -m patchpro_bot.cli run-ci --base-dir src/my_module --artifacts .patchpro
```

### 2. **Pre-Push Analysis**
Analyze changes before pushing:

```bash
# Analyze changes since last push
git diff origin/main...HEAD --name-only | grep '\.py$' | \
  xargs python -m patchpro_bot.cli run-ci --base-dir . --artifacts .patchpro
```

### 3. **Interactive Code Review**
Use PatchPro as a local code reviewer:

```bash
# Analyze current working directory
python -m patchpro_bot.cli analyze . --format table

# Generate patches for fixable issues
python -m patchpro_bot.cli run-ci --base-dir . --artifacts .patchpro

# Apply patches interactively
git apply .patchpro/patch_combined_*.diff
```

### 4. **IDE Integration** (Future)
```bash
# VS Code extension command
# Ctrl+Shift+P -> "PatchPro: Analyze Current File"

# Vim integration
:!python -m patchpro_bot.cli analyze %

# IntelliJ plugin
# Tools -> PatchPro -> Analyze Project
```

## Local Configuration

Create `.patchpro.toml` in your project root:

```toml
[analysis]
tools = ["ruff", "semgrep"]
exclude_patterns = ["tests/", "__pycache__/", ".venv/"]

[ruff]
config_file = "pyproject.toml"
select = ["E", "F", "W", "C90", "I", "N", "D", "UP", "YTT", "ANN", "S", "BLE", "FBT", "B", "A", "COM", "C4", "DTZ", "T10", "EM", "EXE", "ISC", "ICN", "G", "INP", "PIE", "T20", "PYI", "PT", "Q", "RSE", "RET", "SLF", "SIM", "TID", "TCH", "ARG", "PTH", "ERA", "PGH", "PL", "TRY", "FLY", "NPY", "RUF"]

[semgrep]
config = ".semgrep.yml"

[llm]
model = "gpt-4o-mini"
max_tokens = 4000
temperature = 0.1

[output]
artifacts_dir = ".patchpro"
format = "json"
include_patches = true
```

## Git Integration

### Pre-commit Hook
Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run PatchPro on staged files
STAGED_FILES=$(git diff --cached --name-only | grep '\.py$' | tr '\n' ' ')

if [ -n "$STAGED_FILES" ]; then
    echo "🔍 Running PatchPro analysis on staged files..."
    
    # Create temp directory with staged files
    mkdir -p .patchpro/staged
    for file in $STAGED_FILES; do
        cp "$file" ".patchpro/staged/"
    done
    
    # Run analysis
    python -m patchpro_bot.cli run-ci --base-dir .patchpro/staged --artifacts .patchpro
    
    # Check if critical issues found
    if [ -f ".patchpro/report.md" ]; then
        CRITICAL_ISSUES=$(grep -c "error:" .patchpro/report.md || echo "0")
        if [ "$CRITICAL_ISSUES" -gt 0 ]; then
            echo "❌ Critical issues found! Check .patchpro/report.md"
            echo "Run 'git apply .patchpro/patch_combined_*.diff' to apply suggested fixes"
            exit 1
        fi
    fi
    
    echo "✅ PatchPro analysis passed"
fi
```

### Pre-push Hook
Add to `.git/hooks/pre-push`:

```bash
#!/bin/bash
# Run PatchPro on changes since origin/main
echo "🔍 Running PatchPro analysis on push changes..."

CHANGED_FILES=$(git diff origin/main...HEAD --name-only | grep '\.py$' | tr '\n' ' ')

if [ -n "$CHANGED_FILES" ]; then
    python -m patchpro_bot.cli run-ci --base-dir . --artifacts .patchpro
    
    # Show summary
    if [ -f ".patchpro/report.md" ]; then
        echo "📊 PatchPro Summary:"
        grep -E "Total findings|Patches generated" .patchpro/report.md
    fi
fi
```

## Developer Workflow Examples

### Morning Code Review
```bash
# Check what needs attention today
python -m patchpro_bot.cli analyze . --format table

# Focus on high-priority issues
python -m patchpro_bot.cli analyze . --format json | jq '.findings[] | select(.severity == "error")'

# Generate fixes for quick wins
python -m patchpro_bot.cli run-ci --base-dir . --artifacts .patchpro
git apply .patchpro/patch_combined_*.diff
```

### Feature Development
```bash
# Start feature
git checkout -b feature/user-auth

# Develop...
# Test changes with PatchPro
python -m patchpro_bot.cli run-ci --base-dir src/auth --artifacts .patchpro

# Review suggested improvements
cat .patchpro/report.md

# Apply automatic fixes
git apply .patchpro/patch_combined_*.diff

# Commit clean code
git add . && git commit -m "feat: implement user authentication"
```

### Code Quality Gates
```bash
# Before creating PR
python -m patchpro_bot.cli run-ci --base-dir . --artifacts .patchpro

# Ensure no critical issues
CRITICAL=$(grep -c "severity.*error" .patchpro/report.md || echo "0")
if [ "$CRITICAL" -eq 0 ]; then
    echo "✅ Ready for PR"
    git push origin feature/user-auth
else
    echo "❌ Fix critical issues first"
    cat .patchpro/report.md
fi
```

## Benefits for Developers

1. **Early Issue Detection**: Catch problems before they reach CI/CD
2. **Learning Tool**: Understand code quality patterns and best practices  
3. **Time Saving**: Automatic fixes for common issues
4. **Consistency**: Same analysis as CI, no surprises
5. **Offline Capable**: Works without internet (except LLM features)
6. **Customizable**: Adapt rules to team/project standards

## Advanced Features

### 1. **Watch Mode**
```bash
# Auto-analyze on file changes
python -m patchpro_bot.cli watch src/
```

### 2. **Diff-Only Analysis**
```bash
# Only analyze changed lines
python -m patchpro_bot.cli analyze --diff-only --base=origin/main
```

### 3. **Team Configuration**
```bash
# Share team config via git
git add .patchpro.toml
git commit -m "Add team PatchPro config"
```

### 4. **CI Synchronization**
```bash
# Use same config as CI
python -m patchpro_bot.cli run-ci --config-from=.github/workflows/patchpro.yml
```

This local developer workflow makes PatchPro a powerful daily development tool, not just a CI/CD component!