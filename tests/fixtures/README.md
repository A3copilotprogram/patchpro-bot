# Test Fixtures for PatchPro Unit Tests

This directory contains synthetic test files with intentional code quality issues
for testing patch generation without requiring API calls or external dependencies.

## Structure

- `security/` - Security vulnerability examples (HIGH success rate expected: 50-75%)
- `style/` - Style issue examples (LOW success rate expected: 0-25%, marked xfail)
- `imports/` - Import-related issues (MIXED success rate: 20-50%)
- `findings/` - Simulated analyzer outputs (JSON)

## Usage in Tests

```python
from pathlib import Path
import json

# Load finding
fixtures_dir = Path(__file__).parent / "fixtures"
findings = json.loads((fixtures_dir / "findings" / "all_findings.json").read_text())

# Get specific finding
sql_injection_finding = next(f for f in findings if f["rule_id"].endswith("sql-query"))

# Use in test
def test_sql_injection_fix():
    finding = create_finding_from_fixture(sql_injection_finding)
    patch = generator.generate_single_patch(finding)
    assert can_apply_patch(patch)
```

## Regenerating Fixtures

If you need to update fixtures or add new ones:

```bash
python scripts/generate_test_fixtures.py
```

## Expected Success Rates (from TRACE_ANALYSIS.md)

| Category | Rules | Expected Success | Status |
|----------|-------|------------------|--------|
| Security | Semgrep | 50-75% | Should pass |
| Style | F841, E401 | 0-25% | xfail (known issue) |
| Imports (simple) | I001, F401 | 30-50% | Should mostly pass |
| Imports (complex) | I001 complex | 0-20% | xfail (known issue) |

## Adding New Fixtures

1. Add generator function in `scripts/generate_test_fixtures.py`
2. Return finding dict with: tool, rule_id, file, line, message
3. Run script to regenerate fixtures
4. Update tests to use new fixture
