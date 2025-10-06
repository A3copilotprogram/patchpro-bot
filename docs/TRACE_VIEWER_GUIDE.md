# PatchPro Trace Viewer Guide

**Visual debugging tool for patch generation traces**

The Trace Viewer is a Streamlit-based UI for analyzing LLM interactions, failures, and performance metrics captured during patch generation.

---

## Quick Start

### 1. Install Observability Dependencies

```bash
pip install -e ".[observability]"
```

This installs:
- `streamlit` - Web UI framework
- `plotly` - Interactive charts (future use)
- `pandas` - Data analysis (future use)

### 2. Generate Traces (If Needed)

If you don't have traces yet, run PatchPro with agentic mode:

```bash
# From patchpro-bot-agent-dev directory
patchpro analyze-pr --base main --head HEAD --with-llm
```

This creates `.patchpro/traces/`:
- `traces.db` - SQLite database (queryable)
- `*.json` - Individual trace files (human-readable)

### 3. Launch Trace Viewer

```bash
# From patchpro-bot-agent-dev directory
streamlit run trace_viewer.py
```

Opens browser at http://localhost:8501

### 4. Explore Traces

The UI shows:
- **Summary Metrics**: Total traces, success rate, avg cost, avg latency
- **Filters**: Rule ID, status, strategy, text search
- **Trace Cards**: Expandable cards with full details for each attempt

---

## What You Can See

### Per-Trace Information

**Expandable Card Header:**
```
🟢 F401 - example.py:15 - Attempt 1
```
- Status: 🟢 success, 🔴 failed, ⚠️ exhausted_retries
- Rule ID: Ruff/Semgrep rule being fixed
- File and line number
- Retry attempt number

**Card Details:**
1. **Metadata**: Strategy, model, file type, complexity, tokens, cost, latency
2. **Finding**: The original issue message
3. **Prompt**: System + user prompts sent to LLM (collapsed)
4. **LLM Response**: Raw LLM output (collapsed)
5. **Generated Patch**: The unified diff patch (if generated)
6. **Validation Errors**: Git apply errors (if failed)
7. **Previous Errors**: Errors from earlier attempts (if retry)

### Summary Metrics

**Top Banner:**
- Total traces logged
- Success rate (% patches that validated)
- Average cost per patch
- Average latency per patch
- Total cost across all attempts
- Average retry attempt number

### Filters

**Search/Filter By:**
- **Rule ID**: Focus on specific rule types (F401, D100, etc.)
- **Status**: success, failed, exhausted_retries
- **Strategy**: generate_single_patch, generate_batch_patch
- **Text Search**: Find by message text or file path

---

## Use Cases

### 1. Debug Why Patches Fail

**Scenario**: You see low success rate in metrics.

**Steps**:
1. Filter by `Status = failed`
2. Open failed traces
3. Look at **Validation Errors** section
4. Common patterns:
   - "patch does not apply" → Wrong line numbers
   - "malformed patch" → LLM output formatting issue
   - "unexpected end of file" → Multi-line string corruption

**Action**: Use error patterns to improve prompts or add post-processing.

### 2. Analyze Retry Behavior

**Scenario**: Want to see if retries actually help.

**Steps**:
1. Search for same file/line with different attempt numbers
2. Compare **LLM Response** between attempts
3. Check **Previous Errors** section in retry attempts
4. See if LLM learned from feedback

**What to look for**:
- Does attempt 2/3 fix issues from attempt 1?
- Are errors repeated (LLM stuck)?
- Does retry cost justify success rate improvement?

### 3. Identify High-Cost Rules

**Scenario**: Want to optimize token usage.

**Steps**:
1. Look at **Avg Cost** in summary
2. Open traces with highest cost
3. Check **Tokens Used** and **Prompt** length
4. Identify if verbose prompts for certain rules

**Action**: Shorten prompts for high-volume rules.

### 4. Compare Strategies

**Scenario**: Should you use batch or single patch mode?

**Steps**:
1. Filter by `Strategy = generate_batch_patch` → Check success rate
2. Filter by `Strategy = generate_single_patch` → Check success rate
3. Compare costs, latency, success rate

**Current expectation**: Batch likely fails more (0% in some cases).

### 5. Find Good Training Examples

**Scenario**: Building fine-tuning dataset.

**Steps**:
1. Filter by `Status = success`
2. Filter by `Rule ID = F401` (or target rule)
3. Open traces with clean patches
4. Click **"Save as Good Example"** (feature coming soon)

**Future**: Saved examples export to fine-tuning JSON format.

---

## Example Workflow: Fix Batch Patches

**Goal**: Understand why batch patches fail and fix them.

### Step 1: Gather Data
```bash
# Filter for batch patch failures
Filter: Strategy = generate_batch_patch, Status = failed
```

### Step 2: Analyze 10 Failed Traces
Open first 10 failed batch traces. Look for patterns:

**Hypothesis 1: Wrong line numbers in multi-hunk diffs**
- Check patches: Are `@@` hunk headers correct?
- Check validation errors: "patch does not apply to line X"
- Pattern: Second/third hunk has wrong line numbers

**Hypothesis 2: LLM corrupts file content**
- Check patches: Are unchanged lines modified?
- Check validation errors: "unexpected content at line X"
- Pattern: LLM hallucinates code that wasn't there

**Hypothesis 3: Prompt too complex**
- Check prompts: How many findings in one request?
- Pattern: Batch of 5+ findings → higher failure rate

### Step 3: Test Fix
Based on hypothesis, implement fix:

**Hypothesis 1 Fix**: Add post-processing to recalculate hunk headers
**Hypothesis 2 Fix**: Add instruction "DO NOT modify unchanged lines"
**Hypothesis 3 Fix**: Limit batch size to 3 findings max

### Step 4: Measure Improvement
```bash
# Re-run with fix
patchpro analyze-pr --base main --head HEAD --with-llm

# Compare success rates
Old batch success rate: 0%
New batch success rate: ??%
```

### Step 5: Iterate
If success rate improved but still below target (70%), repeat process.

---

## View Traces from CI

### Download Traces from GitHub Actions

If you have traces from CI workflow run:

```bash
# 1. Download artifact from GitHub Actions
# (Currently: artifact upload has path issue, but traces ARE created)

# 2. Extract to local directory
unzip patchpro-traces.zip -d /path/to/traces

# 3. Launch viewer with custom path
streamlit run trace_viewer.py -- --trace-dir /path/to/traces
```

### View Demo Traces from PR #9

**Live example**: Workflow run 18263485405 in patchpro-demo-repo

**What to look for**:
1. Navigate to Actions → run 18263485405
2. Check logs for "Agentic mode: True"
3. See debug output listing trace files:
   ```
   .patchpro/traces/F841_example.py_9_1_*.json
   .patchpro/traces/F841_example.py_9_3_*.json
   ```
4. Notice `attempt_1` and `attempt_3` for same finding → retry worked!

**To view locally** (once artifact upload fixed):
```bash
# Download artifact, then:
streamlit run trace_viewer.py -- --trace-dir ./downloaded-traces
```

---

## Keyboard Shortcuts

- `R` - Rerun app (refresh data)
- `Ctrl+C` in terminal - Stop server
- Browser refresh - Reload page

---

## Troubleshooting

### "No traces database found"

**Cause**: Haven't run PatchPro with agentic mode yet.

**Fix**:
```bash
patchpro analyze-pr --base main --head HEAD --with-llm
```

### Trace viewer doesn't show new traces

**Cause**: Streamlit caches data.

**Fix**: Press `R` to rerun app, or refresh browser.

### Can't install streamlit

**Cause**: Observability dependencies not installed.

**Fix**:
```bash
pip install -e ".[observability]"
```

### Traces exist but not in default location

**Cause**: Traces in custom directory.

**Fix**:
```bash
streamlit run trace_viewer.py -- --trace-dir /path/to/traces
```

---

## Future Enhancements

### Coming in Phase 2.2 (Failure Clustering)
- Automatic clustering of similar failures
- "Top 5 failure modes" section
- Pattern recognition using embeddings

### Coming in Phase 2.3 (Cost Tracking)
- Interactive charts (Plotly)
- Cost trends over time
- Cost by rule category
- Latency distribution histograms

### Coming in Phase 3.4 (Fine-Tuning)
- Export selected traces to fine-tuning JSON
- One-click dataset curation
- Human labeling interface
- Agreement scoring with LLM-as-judge

---

## Tips for Effective Debugging

### 1. Start with Summary Metrics
Don't dive into individual traces immediately. Check:
- What's the overall success rate? (Below 50% → systemic issue)
- What's the retry rate? (High → validation often fails)
- What's the cost? (High → prompts too verbose)

### 2. Filter Strategically
Don't look at all traces. Focus on:
- **First**: Failed traces for most common rule
- **Second**: Successful traces for same rule (compare)
- **Third**: Exhausted retries (hardest cases)

### 3. Look for Patterns, Not Individual Bugs
One failed trace = edge case.
Ten failed traces with same error = systemic issue.

### 4. Compare Prompt vs Response
Most bugs are in the LLM's interpretation of the prompt:
- Is the prompt clear?
- Does it include enough context?
- Does the response follow instructions?

### 5. Check Previous Errors in Retries
If retry fails again, did the LLM:
- Ignore previous error feedback?
- Misunderstand the error?
- Make the same mistake differently?

---

## Related Documentation

- **PATH_TO_MVP.md**: Overall roadmap and Phase 2 plan
- **TELEMETRY_PR_TEST_PLAN.md**: How telemetry was tested in CI
- **DEMO_EVALUATION_GUIDE.md**: How to show traces to judges/stakeholders

---

## Questions?

**How do I share traces with team?**
→ Commit `.patchpro/traces/*.json` to git (or zip and share)

**Can I query traces programmatically?**
→ Yes! Use `telemetry.PatchTracer.query_traces()` API

**Can I use this in CI?**
→ Not yet (Streamlit needs interactive browser), but you can query SQLite in CI scripts

**Where's the clustering feature?**
→ Coming in Phase 2.2 (current focus: manual exploration)

---

**Last Updated**: 2025-10-06  
**Status**: Phase 2.1 Complete 🎉  
**Next**: Phase 2.2 (Failure Clustering)
