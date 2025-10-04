# Local Developer Workflow - Complete Guide

This document describes PatchPro's git hook-based workflow for seamless code quality integration during development.

## Overview

PatchPro integrates into your git workflow using two hooks:

1. **post-commit**: Analyzes your changes in the background after each commit (non-blocking)
2. **pre-push**: Shows findings and offers to apply fixes before pushing (interactive)

This provides a safety net without interrupting your flow.

## Installation

Initialize PatchPro hooks in any git repository:

```bash
cd /path/to/your/repo
python -m patchpro_bot.cli init
```

This installs hooks that:
- Work in regular repos, git worktrees, and submodules
- Use `git rev-parse --git-common-dir` for universal compatibility
- Only analyze Python files (extensible to other languages)

## Complete Workflow Example

### Step 1: Commit Code with Issues

```bash
# Edit a file, introducing some issues
$ cat workflow_demo.py
"""Demo file"""

import json  # unused import
import os    # unused import

def check_user(username):
    if username == None:  # should use 'is None'
        return False
    return True

def handle_error():
    try:
        result = do_something()
        return result
    except:  # bare except - too broad
        return None

# Commit the changes
$ git add workflow_demo.py
$ git commit -m "feat: add user validation"
🤖 PatchPro analyzing your commit in the background...
[main a1b2c3d] feat: add user validation
 1 file changed, 20 insertions(+)
```

**What happens**: The post-commit hook triggers background analysis. Your terminal is not blocked - you can continue working.

### Step 2: Try to Push

```bash
$ git push
```

**What happens**: The pre-push hook runs `python -m patchpro_bot.cli pre-push-prompt`

### Step 3: Review Findings

```
⚠️  PatchPro found 4 issue(s)
   🔴 4 critical issue(s)
   🔧 Patches available in .patchpro/

╭────────────────────────── Analysis Summary ──────────────────────────╮
│ Tool: ruff                                                           │
│ Total Findings: 4                                                    │
╰──────────────────────────────────────────────────────────────────────╯

┏━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ File              ┃ Line ┃ Rule ┃ Severity ┃ Category    ┃ Message                   ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ workflow_demo.py  │    3 │ F401 │ ERROR    │ CORRECTNESS │ `json` imported but       │
│                   │      │      │          │             │ unused                    │
│ workflow_demo.py  │    4 │ F401 │ ERROR    │ CORRECTNESS │ `os` imported but unused  │
│ workflow_demo.py  │   19 │ E711 │ ERROR    │ STYLE       │ Comparison to `None`      │
│                   │      │      │          │             │ should be `cond is None`  │
│ workflow_demo.py  │   30 │ E722 │ ERROR    │ STYLE       │ Do not use bare `except`  │
└───────────────────┴──────┴──────┴──────────┴─────────────┴───────────────────────────┘

Action [fix/push/cancel] (fix):
```

### Step 4: Choose an Action

You have three options:

#### Option A: **fix** (recommended) - Apply patches automatically

```
Action [fix/push/cancel] (fix): fix
Applying patch: patch_001_workflow_demo_20251004_020649.diff
✅ Patch applied successfully
✅ Commit amended with fixes
Continuing with push...

Enumerating objects: 5, done.
Counting objects: 100% (5/5), done.
...
To github.com:user/repo.git
   a1b2c3d..e4f5a6b  main -> main
```

**What happens**:
1. Latest patch is applied: `git apply .patchpro/patch_*.diff`
2. Changes are staged: `git add -u`
3. Commit is amended: `git commit --amend --no-edit`
4. Push proceeds automatically
5. Your commit now has the fixes!

#### Option B: **push** - Push anyway without fixes

```
Action [fix/push/cancel] (fix): push
⚠️  Pushing without applying fixes
```

Use this when you want to push quickly and fix issues later.

#### Option C: **cancel** - Abort the push

```
Action [fix/push/cancel] (fix): cancel
Push cancelled
```

Use this when you want to manually review/fix issues before pushing.

### Step 5: Verify Fixes

```bash
$ git show HEAD:workflow_demo.py
"""Demo file"""


def check_user(username):
    if username is None:  # ✅ Fixed!
        return False
    return True

def handle_error():
    try:
        result = do_something()
        return result
    except Exception:  # ✅ Fixed!
        return None
```

All issues resolved:
- ✅ Removed unused imports (json, os)
- ✅ Fixed `== None` → `is None`
- ✅ Fixed bare `except:` → `except Exception:`

## How It Works

### Post-Commit Hook

Location: `.git/hooks/post-commit`

```bash
#!/bin/bash
# PatchPro post-commit hook

CHANGED_PY=$(git diff-tree --no-commit-id --name-only -r HEAD | grep '\.py$')

if [ -n "$CHANGED_PY" ]; then
    nohup python -m patchpro_bot.cli analyze-staged --async --with-llm --last-commit > /dev/null 2>&1 &
    echo "🤖 PatchPro analyzing your commit in the background..."
fi
```

**Features**:
- Non-blocking: Uses `nohup` and background process (`&`)
- Fast: Only analyzes files changed in last commit
- Smart: Only runs if Python files were modified
- Async: `--async` flag enables background processing
- LLM-powered: `--with-llm` generates patches automatically

### Pre-Push Hook

Location: `.git/hooks/pre-push`

```bash
#!/bin/bash
# PatchPro pre-push hook

python -m patchpro_bot.cli pre-push-prompt

if [ $? -ne 0 ]; then
    exit 1
fi

exit 0
```

**Features**:
- Interactive: Shows findings table and prompts for action
- Smart: Reads analysis from `.patchpro/status.json`
- Safe: Exit code 1 cancels push, 0 allows it
- Flexible: User chooses fix/push/cancel

## Generated Artifacts

PatchPro creates a `.patchpro/` directory with:

```
.patchpro/
├── findings.json           # All findings in structured format
├── ruff.json              # Raw ruff output
├── semgrep.json           # Raw semgrep output
├── status.json            # Current analysis status
├── report.md              # Human-readable report
├── patch_*.diff           # Individual patches per file
├── patch_combined_*.diff  # Combined patch for all files
├── patch_summary_*.md     # Summary of patches
└── patchpro_enhanced.log  # Detailed logs
```

### Patch Format

Patches use git-compatible unified diff format:

```diff
diff --git a/workflow_demo.py b/workflow_demo.py
index 03dee94..ece7713 100644
--- a/workflow_demo.py
+++ b/workflow_demo.py
@@ -1,7 +1,5 @@
 """Demo: Local developer workflow with PatchPro."""
 
-import json  # This import is unused
-import os
 
 
 def process_items(items):
@@ -16,7 +14,7 @@ def process_items(items):
 def check_user(username):
     """Check if username is valid."""
     # Bad: using == None instead of is None
-    if username == None:
+    if username is None:
         return False
     return True
```

**Key features**:
- ✅ Uses **relative paths** from git root (not absolute paths)
- ✅ Preserves **spaces in blank context lines** (` \n`)
- ✅ Valid unified diff format: `git apply --check` passes
- ✅ Safe to apply: `git apply patch.diff` works reliably

## Configuration

Create `.patchpro.toml` in your repo root:

```toml
[analysis]
tools = ["ruff", "semgrep"]
async_mode = true

[ruff]
select = ["F", "E", "W", "I"]
ignore = ["E501"]

[llm]
model = "gpt-4o-mini"
max_tokens = 2000

[hooks]
post_commit = true
pre_push = true
block_on_critical = true
```

## Best Practices

1. **Commit often**: More commits = more granular analysis
2. **Review fixes**: Use `git show` to verify patches before pushing
3. **Keep patches**: `.patchpro/` directory is useful for learning
4. **Trust but verify**: Patches are LLM-generated, review critical changes
5. **Use with CI/CD**: Pre-push is your last line of defense before CI

## Known Limitations

1. **LLM Quality**: Fixes may introduce new issues (e.g., unused variables)
   - **Status**: Quality-of-fix improvements in progress
   - **Workaround**: Review patches before applying

2. **Performance**: Analysis takes 5-10s for typical commits
   - **Status**: Async mode makes this non-blocking
   - **Future**: Incremental analysis for large files

3. **Language Support**: Currently Python-only
   - **Status**: Architecture supports other languages
   - **Future**: JavaScript, TypeScript, Go planned

## Summary

The local dev workflow provides:
- ✅ **Non-blocking**: Analysis happens in background
- ✅ **Interactive**: You choose when to apply fixes
- ✅ **Safe**: Amends commits before push
- ✅ **Fast**: Only analyzes changed files
- ✅ **Smart**: LLM-generated patches automatically fix issues
- ✅ **Reliable**: Git-compatible patches apply cleanly
