# PatchPro: Path to Industry-Standard MVP

**Date**: 2025-10-05  
**Current State**: Research-quality proof-of-concept with 50% file coverage  
**Target**: Industry-standard MVP with >90% coverage and production telemetry

## Current Gaps (Brutal Honesty)

### Missing Evaluation Infrastructure
- ❌ No Level 1 unit tests for patch generation
- ❌ No trace logging (can't see what LLM saw/did)
- ❌ No human eval interface for labeling good/bad patches
- ❌ No LLM-as-judge for automated eval
- ❌ No metrics tracking (precision, recall, coverage over time)

### Missing Observability
- ❌ No logging of:
  - Query rewrites (how findings → prompts)
  - LLM token usage (cost per patch)
  - Retry patterns (which strategies fail/succeed)
  - Failure modes (categorized by type)
  - User metadata (file type, finding complexity, etc.)
- ❌ No dashboards (can't visualize what's happening)
- ❌ No search/filter UI for traces

### Missing Data Curation
- ❌ No synthetic test data generation
- ❌ No labeling UI for creating fine-tuning datasets
- ❌ No clustering of failures to identify patterns
- ❌ No way to turn failures into improved prompts

### Missing Core Functionality
- ❌ Batch patches completely fail (0% success)
- ❌ Complex fixes fail (docstrings, multi-line changes)
- ❌ No comparison to baseline (v1 non-agentic)
- ❌ Unknown performance at scale (only tested 50 findings)

## The Plan: 3-Phase Approach

### Phase 1: Evaluation Foundation (Week 1)
**Goal**: See what's actually happening + measure quality

#### 1.1 Trace Logging
```python
# Log EVERYTHING about each patch attempt
class PatchTrace(BaseModel):
    trace_id: str
    timestamp: datetime
    finding: AnalysisFinding
    prompt: str  # What we sent to LLM
    llm_response: str  # What LLM returned
    patch_generated: Optional[str]
    validation_result: bool
    validation_errors: List[str]
    retry_attempt: int
    strategy: str  # "batch" or "single"
    tokens_used: int
    latency_ms: int
    cost_usd: float
    
    # Metadata for analysis
    file_type: str
    finding_complexity: str  # "simple", "moderate", "complex"
    rule_category: str  # "import-order", "docstring", etc.
```

**Implementation**:
- Add `@trace` decorator to all LLM calls
- Store traces in SQLite (LanceDB later)
- Log to structured JSON for easy parsing

#### 1.2 Unit Tests (Level 1 Evals)
Create assertion-based tests for common patterns:

```python
def test_import_ordering():
    """Test that LLM fixes import ordering correctly"""
    finding = create_test_finding(rule="I001", file="test.py")
    patch = generator.generate_single_patch(finding)
    
    # Assertions
    assert patch is not None, "Should generate patch"
    assert can_apply(patch), "Patch should apply cleanly"
    assert "+from" in patch, "Should have import additions"
    assert no_empty_additions(patch), "No empty + lines"
    assert proper_hunk_headers(patch), "Valid @@ headers"

def test_docstring_formatting():
    """Test docstring fixes"""
    finding = create_test_finding(rule="D100", file="test.py")
    patch = generator.generate_single_patch(finding)
    
    # This will FAIL currently - that's good!
    assert patch is not None
    assert can_apply(patch)
```

**Tests to write**:
- Import ordering (I001) ✅ Should work
- Unused imports (F401) ✅ Should work  
- Docstring formatting (D100) ❌ Currently fails
- Multi-line strings ❌ Currently fails
- Batch patches ❌ Currently fail

Run on every code change in CI.

#### 1.3 Synthetic Test Data Generation
```python
def generate_test_findings(n=100):
    """Generate synthetic findings for testing"""
    # Use LLM to generate realistic code issues
    prompt = """
    Generate 100 Python code snippets with specific issues:
    - 30 import ordering issues (Ruff I001)
    - 30 unused imports (F401)
    - 20 docstring issues (D100-D107)
    - 20 multi-line string formatting
    
    Return as JSON with: code, issue_type, expected_fix
    """
    return llm.generate(prompt)
```

#### 1.4 Metrics Tracking
Store test results over time:

```sql
CREATE TABLE test_runs (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    git_commit TEXT,
    total_tests INT,
    passed INT,
    failed INT,
    pass_rate FLOAT,
    avg_tokens INT,
    avg_cost_usd FLOAT
);

CREATE TABLE test_results (
    id INTEGER PRIMARY KEY,
    run_id INTEGER,
    test_name TEXT,
    passed BOOLEAN,
    error_message TEXT,
    tokens_used INT,
    latency_ms INT
);
```

Visualize in simple dashboard (Metabase/Streamlit).

---

### Phase 2: Observability & Debugging (Week 2)
**Goal**: Understand WHY things fail + make debugging effortless

#### 2.1 Trace Viewing UI
Build lightweight tool to view/filter traces:

```python
# Using Streamlit
import streamlit as st

st.title("PatchPro Trace Viewer")

# Filters
strategy = st.selectbox("Strategy", ["all", "batch", "single"])
status = st.selectbox("Status", ["all", "success", "failed"])
file_type = st.selectbox("File Type", ["all", ".py", ".js", ".ts"])

# Load traces
traces = db.query(f"""
    SELECT * FROM traces 
    WHERE strategy LIKE '%{strategy}%'
    AND status LIKE '%{status}%'
    LIMIT 100
""")

# Display
for trace in traces:
    with st.expander(f"{trace.finding.rule_id} - {trace.status}"):
        st.code(trace.prompt, language="markdown")
        st.code(trace.patch_generated or "No patch", language="diff")
        st.error(trace.validation_errors)
        
        # Edit button for data curation
        if st.button("Mark as good example"):
            save_to_fine_tuning_dataset(trace)
```

**Key features**:
- Search by rule_id, file, error message
- Filter by success/fail, strategy, complexity
- View prompt + response + validation side-by-side
- One-click save to fine-tuning dataset

#### 2.2 Failure Mode Clustering
```python
def cluster_failures():
    """Group failures by similarity to find patterns"""
    failures = db.query("SELECT * FROM traces WHERE status='failed'")
    
    # Embed error messages
    embeddings = embed([f.validation_errors for f in failures])
    
    # Cluster
    clusters = kmeans(embeddings, n_clusters=5)
    
    # Analyze each cluster
    for cluster_id, traces in clusters.items():
        print(f"Cluster {cluster_id}: {len(traces)} failures")
        print(f"Common pattern: {summarize(traces)}")
        print(f"Example error: {traces[0].validation_errors}")
```

**Identify capability gaps**:
- "Batch patches always corrupt line 30" → Fix batch strategy
- "Docstrings missing closing quotes" → Improve prompt
- "Multi-hunk diffs have wrong line numbers" → Add hunk calculation helper

#### 2.3 Cost & Performance Tracking
```python
# Log per-patch metrics
class PatchMetrics(BaseModel):
    total_cost_usd: float
    total_tokens: int
    total_latency_ms: int
    retry_count: int
    final_status: str

# Dashboard queries
avg_cost_per_patch = db.query("SELECT AVG(cost_usd) FROM traces")
cost_by_strategy = db.query("SELECT strategy, AVG(cost_usd) GROUP BY strategy")
slowest_rules = db.query("SELECT rule_id, AVG(latency_ms) ORDER BY latency_ms DESC LIMIT 10")
```

---

### Phase 3: Improvement Loop (Week 3-4)
**Goal**: Systematically improve to >90% coverage

#### 3.1 Fix Batch Patches (Priority #1)
**Current**: 0% success  
**Target**: >70% success

**Debug process**:
1. Look at 10 failed batch patch traces
2. Identify common errors (likely: wrong line numbers in multi-hunk diffs)
3. Hypothesize fix (better prompt? post-processing? different approach?)
4. Test fix on synthetic data
5. Run unit tests - measure improvement
6. Iterate

**Potential fixes**:
- Better prompt instructions for multi-hunk diffs
- Post-processing to recalculate line numbers
- Fallback to individual patches sooner

#### 3.2 Fix Complex Changes (Docstrings, Multi-line)
**Current**: Fail after 3 retries  
**Target**: >80% success

**Approach**:
1. Generate 50 synthetic docstring issues
2. Test current system - capture failures
3. Analyze failure patterns in traces
4. Improve prompts with few-shot examples
5. Add post-processing for quote matching
6. Re-test - measure improvement

#### 3.3 LLM-as-Judge (Automated Eval)
```python
def evaluate_patch_quality(finding, patch):
    """Use LLM to judge if patch correctly fixes issue"""
    prompt = f"""
    Finding: {finding.message}
    Generated Patch:
    ```diff
    {patch}
    ```
    
    Does this patch correctly fix the issue? Answer with JSON:
    {{
        "correct": true/false,
        "reasoning": "...",
        "issues": ["issue1", "issue2"]
    }}
    """
    
    judgment = llm.generate(prompt, response_model=PatchJudgment)
    return judgment
```

**Align with humans**:
1. Human labels 100 patches as good/bad
2. LLM judges same 100 patches
3. Measure agreement (precision/recall)
4. Iterate on judge prompt to improve alignment
5. Use judge for continuous evaluation

#### 3.4 Fine-Tuning Data Curation
Once we have good traces + labeling UI:

```python
# Curate fine-tuning dataset
good_examples = db.query("""
    SELECT prompt, llm_response 
    FROM traces 
    WHERE status='success' AND human_labeled='good'
    LIMIT 1000
""")

# Format for fine-tuning
dataset = [
    {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": trace.prompt},
            {"role": "assistant", "content": trace.llm_response}
        ]
    }
    for trace in good_examples
]

# Fine-tune
model = openai.FineTuning.create(
    model="gpt-4o-mini",
    training_data=dataset
)
```

---

## Success Criteria for MVP

### Functional Requirements
- ✅ **>90% file coverage** - Successfully generates patches for 9/10 files
- ✅ **100% patch quality** - All generated patches apply cleanly
- ✅ **Batch patches work** - >70% success rate for batch strategy
- ✅ **Complex fixes work** - >80% success for docstrings, multi-line changes

### Observability Requirements
- ✅ **Trace every LLM call** - Can see prompt, response, validation for every attempt
- ✅ **Search/filter traces** - Find specific failures quickly
- ✅ **Track metrics over time** - Know if we're improving (test pass rate, cost, latency)
- ✅ **Cluster failures** - Identify top 5 failure modes automatically

### Evaluation Requirements
- ✅ **100+ unit tests** - Cover common patterns, run on every commit
- ✅ **Synthetic test dataset** - 1000+ generated findings for testing
- ✅ **Human eval UI** - Can label 50 patches/hour as good/bad
- ✅ **LLM-as-judge** - >85% agreement with human evaluator

### Performance Requirements
- ✅ **Cost**: <$0.10 per patch on average
- ✅ **Speed**: <10 seconds per patch on average
- ✅ **Baseline comparison**: Match or beat v1 (non-agentic) success rate

---

## Recommended Tool Stack

**Trace Logging**: LangSmith or Weights & Biases  
**Data Viewing**: Custom Streamlit app (build in 1 day)  
**Metrics Tracking**: SQLite + Metabase  
**Unit Tests**: pytest with custom assertions  
**Clustering**: scikit-learn + OpenAI embeddings  
**Fine-Tuning**: OpenAI API  

**Total cost**: <$500/month for tooling

---

## Timeline Estimate

| Week | Focus | Deliverables |
|------|-------|-------------|
| 1 | Evaluation Foundation | Trace logging, unit tests, synthetic data, metrics dashboard |
| 2 | Observability | Trace viewer UI, failure clustering, cost tracking |
| 3 | Fix Batch Patches | Debug, improve prompts, test, measure |
| 4 | Fix Complex Changes | Docstrings, multi-line, LLM-as-judge |
| 5 | Integration & Testing | Real-world testing, baseline comparison, fine-tuning |

**Total**: 5 weeks to industry-standard MVP

---

## Next Immediate Actions

1. **This week**: Implement trace logging + unit tests
2. **Review together**: Look at first 50 traces to understand failures
3. **Prioritize**: Decide which failure mode to fix first (batch vs complex)
4. **Iterate**: Fix → test → measure → repeat

**Key mindset shift**: "You're doing it wrong if you aren't looking at lots of data." - We need to instrument everything NOW, then use that data to systematically improve.

---

Does this plan align with your vision? What should we tackle first?
