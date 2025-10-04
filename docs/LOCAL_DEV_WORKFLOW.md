# PatchPro Local Developer Workflow

## Overview

PatchPro's local developer workflow is designed around a **crucial insight**: developers don't want to wait during commits, but there's usually a significant window of time between committing and pushing.

This workflow leverages that window for **non-blocking analysis** that happens in the background, with an easy review-and-amend step before pushing.

## The Flow

```
┌──────────────┐
│ git commit   │  ← Instant, non-blocking
└──────┬───────┘
       │
       ├─> post-commit hook
       │   └─> Background analysis starts (async)
       │
   [Developer continues working...]
       │
       ├─> Analysis completes in background
       │   └─> Findings + patches ready
       │
┌──────▼──────────────────┐
│ patchpro review-findings│  ← Before pushing
└──────┬──────────────────┘
       │
       ├─> View findings table
       ├─> Auto-apply patches
       └─> Amend commit (optional)
       │
┌──────▼───────┐
│  git push    │  ← Pre-push hook reminds if needed
└──────────────┘
```

## Setup

### Install Git Hooks

```bash
cd your-project/
patchpro init --hooks
```

This installs:
- **post-commit** - Triggers background analysis after each commit
- **pre-push** - Reminds you to review findings before pushing

### Verify Installation

```bash
patchpro doctor
```

## Usage

### 1. Normal Development Flow

```bash
# Make your changes
vim myfile.py

# Commit normally
git commit -am "feat: add new feature"
# 🤖 PatchPro analyzing your commit in the background...
# ✅ Commit completes instantly!

# Continue working...
# (Analysis happens in the background)

# Before pushing, review findings
patchpro review-findings
```

### 2. Review Findings

When you run `patchpro review-findings`:

```
⚠️  PatchPro found 6 issue(s) in your last commit
   🔴 5 critical issue(s)
   🔧 Patches available in .patchpro/

┌─────────────────────────────────────────────────────────────┐
│ File          │ Line │ Severity │ Code    │ Message         │
├─────────────────────────────────────────────────────────────┤
│ quick_test.py │ 7    │ error    │ F401    │ Unused import   │
│ quick_test.py │ 16   │ error    │ E722    │ Bare except     │
│ quick_test.py │ 23   │ error    │ E711    │ None comparison │
└─────────────────────────────────────────────────────────────┘

Action [amend/ignore/manual]: 
```

**Options:**
- **amend** - Auto-apply patches and amend your last commit (recommended)
- **ignore** - Proceed with push, ignore findings
- **manual** - View patch file and apply manually

### 3. Auto-Amend (Recommended)

Choose `amend`:

```
Action [amend/ignore/manual]: amend
✅ Patch applied successfully
✅ Commit amended with fixes

Your commit has been updated with the fixes!
```

Your commit is now updated with fixes. Push confidently:

```bash
git push
```

### 4. Manual Review

Choose `manual` to see patch details:

```
Action [amend/ignore/manual]: manual
View findings in: .patchpro/findings.json
View patch in: .patchpro/patch_001_quick_test.diff
After fixing, run: git commit --amend --no-edit
```

## Check Analysis Status Anytime

```bash
patchpro check-status
```

Output:
```
⚠️  Found 6 issue(s)
   🔴 5 critical
   🔧 Patches available
```

Or if analysis is still running:
```
🤖 Analysis running...
   Files: quick_test.py
```

## Pre-Push Reminder

When you try to push with unreviewed findings:

```bash
git push
```

Output:
```
⚠️  PatchPro found issues in your recent commits
   Run 'patchpro review-findings' to review and fix before pushing

Proceed with push anyway? (y/N)
```

You can:
- Press `N` to review findings first (recommended)
- Press `Y` to push anyway (findings remain for later)

## Configuration

Edit `.patchpro.toml` to customize:

```toml
[analysis]
tools = ["ruff", "semgrep"]
severity_threshold = "warning"  # Only show warnings and errors

[llm]
model = "gpt-4o-mini"
temperature = 0.1

[output]
artifacts_dir = ".patchpro"
```

## Key Benefits

### ✅ Non-Blocking
Commits complete instantly. Analysis happens in the background while you continue working.

### ✅ Perfect Timing Window
Leverages the natural pause between committing and pushing (often minutes to hours).

### ✅ One-Command Fix
`patchpro review-findings` with `amend` option automatically fixes and updates your commit.

### ✅ Non-Intrusive
Only prompts at push time if there are unreviewed findings. Silent otherwise.

### ✅ CI-Like Experience Locally
Same analysis and fixes that would happen in CI, but locally before you push.

## Comparison: Pre-Commit vs Post-Commit

| Aspect | Pre-Commit Hook | Post-Commit Hook (PatchPro) |
|--------|-----------------|------------------------------|
| **Blocking?** | ✅ Yes - waits for analysis | ❌ No - instant commit |
| **User Experience** | Frustrating delays | Smooth, natural flow |
| **Timing** | During commit | After commit, before push |
| **Fix Approach** | Block commit until fixed | Review and amend later |
| **Adoption** | Developers bypass/disable | Developers embrace |

## Advanced: Manual Trigger

If hooks aren't installed, manually trigger analysis:

```bash
# After committing
patchpro analyze-staged --async --with-llm --last-commit

# Check status
patchpro check-status

# Review when ready
patchpro review-findings
```

## Troubleshooting

### Hook Not Running?

```bash
# Check hooks exist
ls -la .git/hooks/

# Re-install
patchpro init --hooks

# Test manually
python -m patchpro_bot.cli analyze-staged --last-commit --with-llm
```

### Analysis Takes Too Long?

Disable LLM for faster analysis (findings only, no patches):

Edit hooks:
```bash
# In .git/hooks/post-commit, remove --with-llm flag
nohup python -m patchpro_bot.cli analyze-staged --async --last-commit > /dev/null 2>&1 &
```

### Want Immediate Feedback?

For critical files, run analysis before committing:

```bash
patchpro analyze myfile.py
# Review findings immediately
# Then commit
git commit -m "feat: add feature"
```

## Best Practices

1. **Review before pushing** - Use the natural window between commit and push
2. **Amend when possible** - Keep your commit history clean with fixes
3. **Check status periodically** - Run `patchpro check-status` while working
4. **Configure thresholds** - Adjust severity levels in `.patchpro.toml`
5. **Use with pre-commit hooks for formatting** - PatchPro for fixes, pre-commit for formatting

## Examples

### Example 1: Quick Fix Flow

```bash
# Commit
git commit -m "fix: resolve bug"
# 🤖 Background analysis starts...

# Continue working...
# (2 minutes later)

# Review before lunch
patchpro review-findings
# Choose: amend
# ✅ Commit updated with fixes

# Push
git push
```

### Example 2: Ignore and Push

```bash
git commit -m "wip: experimental code"
# Later...
patchpro review-findings
# Choose: ignore
# Findings cleared

git push  # No warnings
```

### Example 3: Manual Review

```bash
git commit -m "feat: add API endpoint"
# Later...
patchpro review-findings
# Choose: manual
# Review .patchpro/patch_001_*.diff
# Apply custom fixes
git commit --amend --no-edit
git push
```

## FAQ

**Q: Does this slow down my commits?**  
A: No! Commits are instant. Analysis runs in the background after committing.

**Q: What if I forget to review?**  
A: The pre-push hook reminds you before pushing.

**Q: Can I disable the hooks?**  
A: Yes, just delete `.git/hooks/post-commit` and `.git/hooks/pre-push`.

**Q: Does this work with multiple commits?**  
A: Yes! Each commit triggers analysis. Review findings for any recent commit.

**Q: What if I'm offline?**  
A: Static analysis (ruff/semgrep) works offline. LLM patch generation requires API access.

**Q: Can I use this in CI too?**  
A: Yes! See [USAGE_MODES.md](./USAGE_MODES.md) for CI integration.

---

**Next:** [USAGE_MODES.md](./USAGE_MODES.md) - All three ways to use PatchPro  
**Next:** [DEMO_GUIDE.md](./DEMO_GUIDE.md) - Step-by-step demos
