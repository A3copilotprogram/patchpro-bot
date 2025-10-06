# PatchPro Test Suite

## Test Files Overview

### Unit Tests

- **`test_models.py`**: Data model validation (Location, Finding, etc.)
- **`test_analysis.py`**: Analyzer and normalizer tests
- **`test_llm.py`**: LLM client and response parsing tests
- **`test_diff.py`**: Diff generation and validation tests

### Integration Tests

- **`test_agentic_core.py`**: Agentic core tool execution
- **`test_agentic_v2.py`**: AgenticPatchGeneratorV2 integration
- **`test_agentic_self_correction.py`**: Self-correction and retry logic
- **`test_agentic_e2e.py`**: End-to-end agentic workflows

### Quality Tests (NEW - Phase 1.2)

- **`test_patch_quality.py`**: **Patch generation quality benchmarks**

## test_patch_quality.py - Quality Benchmark Suite

**Purpose**: Track patch generation success rates and measure improvement over time.

Based on comprehensive trace analysis (see `docs/TRACE_ANALYSIS.md`), this test suite establishes a baseline and targets for improvement.

### Test Categories

#### Category 1: High-Success Patterns (Security Fixes)
- **Expected**: >=50% pass rate
- **Trace analysis**: 75% success rate
- **Tests**:
  - SQL injection fixes (parameterized queries)
  - Insecure hash algorithm upgrades (SHA-1 → SHA-256)
  - Hardcoded secret removal (→ environment variables)

**Status**: Should PASS

#### Category 2: Known-Failure Patterns (Mechanical Fixes)
- **Expected**: 0-25% pass rate
- **Trace analysis**: 0-25% success rate
- **Tests** (marked as `xfail`):
  - Unused variable removal (F841) - corrupt patches
  - Multiple imports per line (E401) - corrupt patches
  - Import ordering in complex files (I001) - context mismatch

**Status**: EXPECTED TO FAIL (xfail) - documents baseline

#### Category 3: Simple Cases
- **Expected**: >=50% pass rate
- **Tests**:
  - Unused imports in simple files (F401)
  - Import ordering in simple files (I001)

**Status**: Should have mixed results

#### Category 4: Retry Effectiveness
- **Expected**: Some improvement with retries
- **Status**: Deferred (requires retry logic mocking)

### Running the Tests

```bash
# Run all quality tests
pytest tests/test_patch_quality.py -v

# Run only passing tests (exclude xfail)
pytest tests/test_patch_quality.py -v -m "not xfail"

# Run only security fix tests
pytest tests/test_patch_quality.py::TestSecurityFixes -v

# Run with detailed output
pytest tests/test_patch_quality.py -v --tb=long
```

### Expected Baseline Results

**Before Phase 3 fixes** (current):
- Category 1 (Security): 2-3/3 pass (66-100%) ✓
- Category 2 (Mechanical): 0/3 pass (0%) ✗ xfail
- Category 3 (Simple): 1-2/2 pass (50-100%) ✓
- **Overall: ~30-50% pass rate**

**After Phase 3.1-3.2 fixes** (corrupt patch + JSON parsing):
- Expected: ~50-60% pass rate
- Category 2 may improve to 25-30%

**After Phase 3.3 fixes** (skip mechanical):
- Expected: ~70% pass rate
- Category 2 removed from scoring (routed to ruff --fix)

**Final target**: >90% pass rate

### Interpreting Results

#### Success Criteria
- ✅ Pass rate matches or exceeds trace analysis baseline (29.4%)
- ✅ Security fixes have >=50% pass rate
- ✅ xfail tests document known failures without failing CI

#### Failure Indicators
- ❌ Pass rate < 20% - investigate setup or LLM issues
- ❌ Security fixes fail - check LLM API or prompts
- ❌ xfail tests pass unexpectedly - good news, but update expectations!

### Integration with CI

Add to GitHub Actions workflow:

```yaml
- name: Run quality benchmark tests
  run: |
    pytest tests/test_patch_quality.py -v --junit-xml=quality-results.xml
    
- name: Upload quality metrics
  uses: actions/upload-artifact@v3
  with:
    name: quality-metrics
    path: quality-results.xml
```

### Tracking Improvement

After each Phase 3 fix:

1. **Run tests**: `pytest tests/test_patch_quality.py -v`
2. **Record pass rate**: Note percentage in commit message
3. **Compare to baseline**: Current rate vs previous rate
4. **Update expectations**: If xfail tests start passing, remove xfail marker

**Example commit message**:
```
fix(patches): Add hunk header post-processing [Phase 3.1]

Fixes corrupt patch errors by validating and recalculating line numbers.

Quality metrics:
- Before: 30% pass rate (3/10 tests)
- After: 50% pass rate (5/10 tests)
- Improvement: +20 percentage points
- Category 2 improvement: 0% → 33% (1/3 tests now pass)

Related: docs/TRACE_ANALYSIS.md Phase 3.1
```

### Test Data Sources

Tests use both:
- **Synthetic data**: Simple, focused code snippets for isolated testing
- **Real-world examples**: Based on actual trace analysis findings

For more realistic testing, see `tests/sample_data/` directory.

### Future Enhancements

- [ ] Add retry effectiveness tests (Category 4)
- [ ] Add batch patch quality tests
- [ ] Add performance benchmarks (latency, cost)
- [ ] Add LLM-as-judge evaluation
- [ ] Generate test data from trace clustering

---

## Related Documentation

- **Trace Analysis**: `docs/TRACE_ANALYSIS.md` - Detailed failure pattern analysis
- **PATH_TO_MVP**: `docs/PATH_TO_MVP.md` - Overall improvement roadmap
- **Trace Viewer**: `docs/TRACE_VIEWER_GUIDE.md` - Visual debugging tool

---

**Last Updated**: 2025-10-06  
**Status**: Phase 1.2 - Baseline tests created  
**Next**: Run tests to establish baseline, then implement Phase 3 fixes
