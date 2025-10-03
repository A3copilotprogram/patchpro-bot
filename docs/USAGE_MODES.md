# PatchPro Usage Modes

PatchPro supports multiple workflows to fit different team needs and existing CI/CD setups.

## 🎯 Three Ways to Use PatchPro

### 1. **All-in-One Mode** (Individual Developers)

PatchPro runs analysis tools AND generates patches.

```bash
# One command does everything
patchpro run-ci

# With specific tools
patchpro run-ci --tools ruff --tools semgrep
```

**Best for:**
- Individual developers
- Quick setup
- Teams without existing static analysis

**Pros:**
- ✅ Simple - one command
- ✅ Fast setup - no configuration needed
- ✅ Consistent results

---

### 2. **Integration Mode** (Enterprise Teams)

PatchPro uses your existing static analysis outputs.

```bash
# Your existing CI already runs these
ruff check --output-format json . > ruff.json
semgrep --json --config auto . > semgrep.json

# PatchPro generates patches from existing results
patchpro generate-patches ruff.json semgrep.json
```

**Best for:**
- Enterprise teams
- Existing CI/CD pipelines
- Teams with custom analysis tools

**Pros:**
- ✅ No duplicate analysis
- ✅ Faster execution
- ✅ Works with ANY static analysis tool
- ✅ Fits existing workflows

---

### 3. **Hybrid Mode** (Smart Auto-Detection)

PatchPro checks for existing findings first.

```bash
# Run with --from-findings flag
patchpro run-ci --from-findings existing_ruff.json --from-findings existing_semgrep.json

# Falls back to running tools if not provided
patchpro run-ci  # Runs tools if no findings exist
```

**Best for:**
- Flexible workflows
- Mixed team environments
- Gradual adoption

**Pros:**
- ✅ Efficient - uses existing data when available
- ✅ Flexible - runs tools when needed
- ✅ Smart - adapts to context

---

## 📊 Comparison

| Feature | All-in-One | Integration | Hybrid |
|---------|------------|-------------|--------|
| **Setup Time** | 1 minute | 5-10 minutes | 5 minutes |
| **Execution Speed** | Medium (runs tools) | Fast (skip tools) | Smart |
| **Tool Flexibility** | Ruff/Semgrep only | Any tool | Any tool |
| **CI Integration** | New workflow | Existing workflow | Both |
| **Best for** | Individuals | Enterprises | Mixed teams |

---

## 🚀 Examples

### Example 1: Quick Local Development

```bash
# Clone repo
git clone https://github.com/your-org/your-repo
cd your-repo

# Run PatchPro
patchpro run-ci

# Apply patches
git apply artifact/patch_combined_*.diff
```

### Example 2: Existing CI Integration

```yaml
# .github/workflows/code-quality.yml
jobs:
  analyze:
    steps:
      # Existing analysis
      - name: Run Ruff
        run: ruff check --output-format json . > ruff.json
      
      - name: Run Semgrep
        run: semgrep --json . > semgrep.json
      
      # NEW: Generate patches from existing results
      - name: Generate Patches
        run: |
          patchpro generate-patches ruff.json semgrep.json --artifacts patches/
          
      - name: Post PR Comment
        uses: actions/upload-artifact@v4
        with:
          name: patches
          path: patches/
```

### Example 3: Pre-commit Hook

```bash
# Initialize PatchPro hooks
patchpro init --hooks

# Now git commit will analyze staged files
git add file.py
git commit -m "Add feature"
# → PatchPro shows findings and offers to apply patches
```

---

## 🔧 Advanced Configuration

### Custom Tool Support

PatchPro automatically detects tool types from filename or content:

```bash
# These all work
patchpro generate-patches ruff_output.json
patchpro generate-patches semgrep_results.json
patchpro generate-patches pylint_report.json
patchpro generate-patches custom_analysis.json  # Generic support
```

### Combining Multiple Tools

```bash
# Analyze with multiple tools
patchpro generate-patches \
  findings/ruff.json \
  findings/semgrep.json \
  findings/pylint.json \
  findings/mypy.json \
  --artifacts combined_patches/
```

### CI/CD Best Practices

1. **Cache analysis results** to avoid re-running expensive tools
2. **Run PatchPro in parallel** with other CI jobs
3. **Post patches as PR comments** for easy review
4. **Auto-apply safe fixes** in separate commits

---

## 💡 Choosing the Right Mode

**Start with All-in-One** if you're:
- Just trying PatchPro
- Working on personal projects
- Building a new workflow

**Move to Integration Mode** when you:
- Have existing CI pipelines
- Use custom analysis tools
- Need faster execution
- Want to avoid duplicate work

**Use Hybrid Mode** for:
- Large teams with varying needs
- Gradual adoption
- Maximum flexibility

---

## 📚 Next Steps

- [Local Developer Guide](./LOCAL_DEVELOPER_GUIDE.md) - Git hooks and watch mode
- [CI/CD Integration](./GITHUB_ACTIONS.md) - Full automation
- [Configuration](./CONFIGURATION.md) - Customize settings
