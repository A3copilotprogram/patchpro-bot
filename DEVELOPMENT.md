# PatchPro Development Guide

This guide helps collaborators set up and run PatchPro locally for development and testing.

## Prerequisites

- **Python 3.12+** (required)
- **uv** package manager (recommended) or pip
- **OpenAI API Key** (for LLM features)

## Quick Setup

### 1. Clone and Setup Environment

```bash
git clone <repository-url>
cd patchpro-bot-agent-dev
```

### 2. Install Dependencies

**Using uv (recommended):**
```bash
uv sync
```

**Using pip:**
```bash
python -m venv .venv
source .venv/bin/activate  # or `.venv/bin/activate.fish` for fish shell
pip install -e .
```

### 3. Configure OpenAI API Key

Create a `.env` file in the project root:
```bash
# .env
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
```

**Get your API key from:** https://platform.openai.com/api-keys

## Running PatchPro Locally

### Option 1: Test with Demo Repository

```bash
# Clone the demo repository
git clone <demo-repo-url>
cd patchpro-demo-repo

# Generate analysis artifacts
mkdir -p artifact/analysis
ruff check --output-format json . > artifact/analysis/ruff_output.json || true
semgrep --config .semgrep.yml --json . > artifact/analysis/semgrep_output.json || true

# Run PatchPro (from demo repo)
uv run --with /path/to/patchpro-bot-agent-dev python -m patchpro_bot.run_ci
```

### Option 2: Test with Your Own Repository

1. **Setup your repository:**
   ```bash
   cd your-repository
   
   # Add proper pyproject.toml
   cat > pyproject.toml << EOF
   [project]
   name = "your-project"
   version = "0.1.0"
   requires-python = ">=3.8"
   dependencies = []
   
   [build-system]
   requires = ["setuptools>=68", "wheel"]
   build-backend = "setuptools.build_meta"
   EOF
   ```

2. **Generate analysis:**
   ```bash
   mkdir -p artifact/analysis
   ruff check --output-format json . > artifact/analysis/ruff_output.json || true
   semgrep --json . > artifact/analysis/semgrep_output.json || true
   ```

3. **Run PatchPro:**
   ```bash
   uv run --with /path/to/patchpro-bot-agent-dev python -m patchpro_bot.run_ci
   ```

### Option 3: Run from Agent Repository

```bash
cd patchpro-bot-agent-dev

# Point to external artifacts
PP_ARTIFACTS=/path/to/repo/artifact uv run python -m patchpro_bot.run_ci
```

## Understanding the Output

PatchPro generates several artifacts in the `artifact/` directory:

- **`report.md`** - Comprehensive analysis report
- **`patch_combined_*.diff`** - AI-generated code fixes
- **`patch_summary_*.md`** - Summary of changes
- **`analysis/`** - Raw analysis data from tools

## Configuration Options

### Environment Variables

- `OPENAI_API_KEY` - OpenAI API key for LLM features
- `PP_ARTIFACTS` - Path to artifacts directory (default: `artifact`)

### Model Settings (optional)

Add to your `.env` file:
```bash
OPENAI_MODEL=gpt-4o-mini        # Default model
OPENAI_MAX_TOKENS=8192          # Max response tokens
OPENAI_TEMPERATURE=0.1          # Generation temperature
```

## Troubleshooting

### Python Version Issues
```bash
# Check Python version
python --version  # Should be 3.12+

# Use specific Python version with uv
uv python install 3.12
uv venv --python 3.12
```

### API Key Issues
```bash
# Test API key
export OPENAI_API_KEY="your-key"
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

### File Path Issues
- Ensure you're running from the correct directory
- Check that source files exist in the expected locations
- Verify `PP_ARTIFACTS` path is correct

### Missing Dependencies
```bash
# Reinstall dependencies
uv sync --force
# or
pip install -e . --force-reinstall
```

## Development Workflow

1. **Make Changes** to PatchPro code
2. **Test Locally** using one of the methods above
3. **Check Logs** in `artifact/patchpro_enhanced.log`
4. **Review Output** patches and reports
5. **Commit Changes** when satisfied

## Performance Notes

- **First run** may be slower (model initialization)
- **Subsequent runs** benefit from caching
- **Large repositories** are processed in intelligent batches
- **API costs** vary by model and code complexity

## Getting Help

- Check logs in `artifact/patchpro_enhanced.log`
- Review error messages for specific issues
- Ensure all prerequisites are met
- Verify file paths and permissions