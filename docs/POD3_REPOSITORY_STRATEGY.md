# Pod 3: CI/DevEx Integration - Repository Strategy

**Date**: October 3, 2025  
**Question**: Where should CI/DevEx workflows be implemented?

---

## 🎯 Answer: **BOTH Repositories** (Different Purposes)

You have two repositories with different roles:

### 1. **patchpro-bot** (Main Tool Repository)
**URL**: `https://github.com/denis-mutuma/patchpro-bot`  
**Current Branch**: `feature/analyzer-rules`  
**Purpose**: The PatchPro tool itself (Python package)

### 2. **patchpro-demo-repo** (Testing Repository)
**URL**: `https://github.com/A3copilotprogram/patchpro-demo-repo`  
**Purpose**: Demo repository to TEST PatchPro on

---

## 📋 What Goes Where?

### ✅ In **patchpro-bot** (Main Tool Repo)

Create `.github/workflows/` for **testing the tool itself**:

```yaml
# .github/workflows/test-patchpro.yml
# Purpose: Test that PatchPro works correctly
# Runs on: PRs to patchpro-bot repository
```

**What to implement here**:
1. ✅ **Package tests** - Test the Python package
2. ✅ **Unit tests** - Test individual modules (llm/, diff/, etc.)
3. ✅ **Integration tests** - Test agent_core.py workflow
4. ✅ **Linting** - Ruff on the PatchPro codebase
5. ❌ **NOT PR comment posting** - This repo has no code issues to fix

**Example workflow**:
```yaml
name: Test PatchPro Package

on:
  pull_request:
    branches: [main, feature/*]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      # Test the package
      - name: Install dependencies
        run: pip install -e ".[dev]"
      
      - name: Run tests
        run: pytest tests/ -v --cov
      
      - name: Run linters
        run: |
          ruff check src/
          mypy src/
```

---

### ✅ In **patchpro-demo-repo** (Testing Repo)

Create `.github/workflows/` for **running PatchPro AS A USER would**:

```yaml
# .github/workflows/patchpro.yml
# Purpose: Run PatchPro on PRs to demonstrate it
# Runs on: PRs to patchpro-demo-repo
```

**What to implement here**:
1. ✅ **Install PatchPro** - From the main repo
2. ✅ **Run analysis** - Ruff/Semgrep on demo code
3. ✅ **Generate fixes** - Use agent_core.py
4. ✅ **Post PR comments** - Show results in PR
5. ✅ **Sticky comments** - Update existing comment
6. ✅ **Pod 4 evaluation** - Test against golden PRs

**Example workflow**:
```yaml
name: PatchPro CI Bot

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  patchpro:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      # Install PatchPro from main repo
      - name: Install PatchPro
        run: |
          pip install git+https://github.com/denis-mutuma/patchpro-bot.git@feature/integrated-agent
      
      # Run PatchPro
      - name: Run PatchPro Analysis
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          patchpro run --analysis-dir ./
      
      # Post results as PR comment
      - name: Post PR Comment
        uses: actions/github-script@v7
        with:
          script: |
            // Read PatchPro output
            const fs = require('fs');
            const report = fs.readFileSync('artifact/report.md', 'utf8');
            
            // Find existing comment (sticky)
            const comments = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
            });
            
            const botComment = comments.data.find(c => 
              c.user.login === 'github-actions[bot]' &&
              c.body.includes('🤖 PatchPro Analysis')
            );
            
            const body = `## 🤖 PatchPro Analysis\n\n${report}`;
            
            // Update or create comment (sticky!)
            if (botComment) {
              await github.rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: botComment.id,
                body: body,
              });
            } else {
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body: body,
              });
            }
```

---

## 🏗️ Repository Architecture

```
┌────────────────────────────────────────────────────────────┐
│  patchpro-bot (Main Tool)                                  │
│  https://github.com/denis-mutuma/patchpro-bot             │
├────────────────────────────────────────────────────────────┤
│  src/patchpro_bot/                                         │
│    ├── agent_core.py         ← The AI agent                │
│    ├── llm/, diff/, analysis/ ← Modules                    │
│    └── cli.py                ← CLI commands                │
│                                                             │
│  .github/workflows/                                         │
│    └── test-patchpro.yml     ← Test the package           │
│                                                             │
│  tests/                      ← Unit/integration tests      │
│  docs/                       ← Documentation               │
└────────────────────────────────────────────────────────────┘
                            │
                            │ pip install
                            ▼
┌────────────────────────────────────────────────────────────┐
│  patchpro-demo-repo (Testing Ground)                       │
│  https://github.com/A3copilotprogram/patchpro-demo-repo   │
├────────────────────────────────────────────────────────────┤
│  src/                                                       │
│    └── example_code.py      ← Code with issues            │
│                                                             │
│  .github/workflows/                                         │
│    └── patchpro.yml         ← Run PatchPro on PRs ✨      │
│                                                             │
│  golden_prs/                ← Pod 4: Test cases            │
│    ├── pr_001.json                                         │
│    └── pr_002.json                                         │
└────────────────────────────────────────────────────────────┘
```

---

## 📝 Implementation Checklist

### Phase 1: Setup **patchpro-bot** Testing (Optional but Recommended)

```bash
cd /home/mutuma/AI\ Projects/patchpro-bot
mkdir -p .github/workflows
```

Create `.github/workflows/test-patchpro.yml`:
- [ ] Test suite runs on PRs
- [ ] Linting with Ruff
- [ ] Type checking with mypy
- [ ] Coverage reporting

**Why**: Ensures PatchPro itself is high quality

---

### Phase 2: Setup **patchpro-demo-repo** CI/DevEx ✨ **THIS IS POD 3**

```bash
# Clone or navigate to demo repo
cd /path/to/patchpro-demo-repo
mkdir -p .github/workflows
```

Create `.github/workflows/patchpro.yml`:
- [x] Install PatchPro from main repo
- [x] Run Ruff/Semgrep analysis
- [x] Generate fixes with agent_core
- [x] Post results as PR comment
- [x] Implement sticky comments (update existing)
- [x] Add artifacts for patches

**Why**: This is the actual Pod 3 deliverable - comment-only vertical slice

---

### Phase 3: Pod 4 in **patchpro-demo-repo**

Create golden test cases:
- [ ] 3-5 PRs with known issues
- [ ] Expected outputs
- [ ] Evaluation metrics
- [ ] LLM-as-judge

**Why**: Validate PatchPro works correctly

---

## 🎯 Sprint-0 Goal Achievement

### Pod 3: CI/DevEx Integration

**Where**: `patchpro-demo-repo/.github/workflows/patchpro.yml`

**Deliverable**: A PR comment bot that:
1. ✅ Detects code issues (Ruff/Semgrep)
2. ✅ Generates fixes (PatchPro agent)
3. ✅ Posts markdown report as comment
4. ✅ Updates comment on new pushes (sticky)

**NOT doing** (beyond Sprint-0):
- ❌ Automatically creating commits
- ❌ Opening draft PRs with fixes
- ❌ Auto-merging changes

---

## 🚀 Recommended Order

### Step 1: Check if patchpro-demo-repo exists locally

```bash
ls -la ~/AI\ Projects/ | grep demo
# or
find ~ -name "patchpro-demo-repo" 2>/dev/null
```

### Step 2A: If exists, navigate to it
```bash
cd /path/to/patchpro-demo-repo
git status
```

### Step 2B: If NOT exists, clone it
```bash
cd ~/AI\ Projects/
git clone https://github.com/A3copilotprogram/patchpro-demo-repo.git
cd patchpro-demo-repo
```

### Step 3: Create the workflow
```bash
mkdir -p .github/workflows
# I'll help you create patchpro.yml
```

### Step 4: Test locally
```bash
# Install PatchPro from your integrated branch
pip install -e ../patchpro-bot

# Run manually to test
patchpro run --analysis-dir ./src/
```

### Step 5: Push and create test PR
```bash
git checkout -b test-patchpro-ci
git add .github/
git commit -m "feat: add PatchPro CI workflow"
git push origin test-patchpro-ci
# Create PR on GitHub to test
```

---

## 💡 Key Insight

The commit messages from your earlier analysis mentioned:

> "Update submodules after rebase and push of ci/devex-github-actions"

This suggests the workflow **already exists** in `patchpro-demo-repo`! Let me help you check:

```bash
# If you have the demo repo, check for existing workflows
cd /path/to/patchpro-demo-repo
ls -la .github/workflows/

# Check git history for CI work
git log --all --oneline | grep -i "ci\|workflow\|devex"
```

---

## 🎯 My Recommendation

### **Do this NOW**:

1. **Find or clone patchpro-demo-repo**
   ```bash
   cd ~/AI\ Projects/
   git clone https://github.com/A3copilotprogram/patchpro-demo-repo.git
   ```

2. **Check if workflow exists**
   ```bash
   cd patchpro-demo-repo
   ls .github/workflows/
   ```

3. **If it exists**: Update it to use your integrated agent
4. **If it doesn't**: I'll help you create it from scratch

### **Don't do this** (for Sprint-0):
- ❌ Don't add workflows to `patchpro-bot` for comment posting
- ❌ Don't try to make PatchPro comment on its own PRs
- ❌ Save that for testing the package quality

---

## 📋 Summary Table

| Task | Repository | Purpose |
|------|------------|---------|
| **Pod 3: CI/DevEx Workflow** | `patchpro-demo-repo` | Run PatchPro on PRs, post comments |
| **PR Comment Posting** | `patchpro-demo-repo` | Show fixes in PR comments |
| **Sticky Comments** | `patchpro-demo-repo` | Update comment on new commits |
| **Pod 4: Golden PRs** | `patchpro-demo-repo` | Test cases for evaluation |
| **Package Testing** | `patchpro-bot` | Test PatchPro code quality |
| **Unit Tests** | `patchpro-bot` | Test modules work correctly |

---

## ✅ Next Action

**Tell me**: Do you have `patchpro-demo-repo` cloned locally?

- **YES** → I'll help you navigate to it and check for existing workflows
- **NO** → I'll help you clone it and create the workflow from scratch

Then we'll implement Pod 3 there! 🚀

---

*This is the correct separation of concerns for Sprint-0*
