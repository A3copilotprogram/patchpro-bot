# PatchPro Agent - Quick Reference

## Installation

```bash
pip install -e .
export OPENAI_API_KEY='your-api-key'
```

## Basic Usage

```bash
# Step 1: Analyze code
patchpro analyze your_code.py --output findings.json

# Step 2: Generate fixes
patchpro agent findings.json --output fixes.md

# Step 3: Review
cat fixes.md
```

## Common Commands

### Analyze Only
```bash
patchpro analyze src/ --output findings.json --format json
```

### Generate Fixes with Specific Model
```bash
patchpro agent findings.json --model gpt-4o --output fixes.md
```

### Full Workflow
```bash
patchpro analyze . --output findings.json && \
patchpro agent findings.json --output report.md
```

## Environment Variables

```bash
# Required
export OPENAI_API_KEY='sk-...'

# Optional
export PATCHPRO_MODEL='gpt-4o-mini'
export PATCHPRO_MAX_TOKENS='2000'
export PATCHPRO_TEMPERATURE='0.1'
```

## Configuration

Default settings (can be customized in code):
- **Model**: gpt-4o-mini (cost-effective)
- **Max tokens**: 2000
- **Temperature**: 0.1 (deterministic)
- **Batch size**: 5 findings
- **Max diff lines**: 50

## Output Format

The agent generates markdown with:
- Summary of findings
- Grouped fixes by file
- Unified diff format
- Confidence indicators (✅⚠️❓)
- Explanations for each fix

## Troubleshooting

**"OpenAI API key not provided"**
```bash
export OPENAI_API_KEY='your-key'
```

**"Module 'openai' not found"**
```bash
pip install openai
```

**"Could not load source files"**
- Check `--base-path` argument
- Ensure files are accessible

## Examples

### Example 1: Single File
```bash
patchpro analyze script.py -o findings.json
patchpro agent findings.json -o fixes.md
```

### Example 2: Full Project
```bash
patchpro analyze src/ \
  --tools ruff semgrep \
  --output findings.json

patchpro agent findings.json \
  --base-path . \
  --output report.md
```

### Example 3: Custom Model
```bash
patchpro agent findings.json \
  --model gpt-4o \
  --output fixes.md
```

## API Usage

```python
from pathlib import Path
from patchpro_bot.agent import PatchProAgent, AgentConfig, load_source_files
from patchpro_bot.analyzer import FindingsAnalyzer

# Load findings
analyzer = FindingsAnalyzer()
findings = analyzer.load_and_normalize("artifact/analysis")

# Load source files
source_files = load_source_files(findings, Path("."))

# Configure and run agent
config = AgentConfig(model="gpt-4o-mini", api_key="sk-...")
agent = PatchProAgent(config)
result = agent.process_findings(findings, source_files)

# Generate report
report = agent.generate_markdown_report(result)
print(report)
```

## Cost Estimate

Using **gpt-4o-mini**:
- ~$0.0002 per fix
- ~$0.002 for 10 fixes
- ~$0.02 for 100 fixes

Very cost-effective for CI/CD use!

## Next Steps

1. Review generated fixes
2. Apply changes manually or use diffs
3. Run tests
4. Commit changes

## Links

- [Full Agent Guide](agent_guide.md)
- [Implementation Details](AGENT_IMPLEMENTATION.md)
- [Requirements](requirements.md)
