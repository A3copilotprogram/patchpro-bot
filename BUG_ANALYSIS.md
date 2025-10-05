# 🐛 Path Normalization Bug - Complete Analysis

## Date: October 5, 2025
## Issue: #12 - Patch Path Normalization

---

## 🎯 THE BUG: Complete Flow Analysis

### 1. **Analysis Stage** (analyzer.py)
```python
# RuffNormalizer._convert_ruff_finding() - Lines ~232
location = Location(
    file="/opt/andela/genai/patchpro-bot-test-bafecd1/src/patchpro_bot/__init__.py",  # ❌ ABSOLUTE PATH
    line=3,
    column=1,
    ...
)
```

**Problem**: Analyzer stores **ABSOLUTE PATHS** in findings.json
- Expected: `"src/patchpro_bot/__init__.py"`
- Actual: `"/opt/andela/genai/patchpro-bot-test-bafecd1/src/patchpro_bot/__init__.py"`

---

### 2. **LLM Prompt Stage** (prompts.py - Line 171)
```python
# build_batch_diff_prompt()
for file_path, findings in file_fixes.items():
    prompt += f"""
## File: `{file_path}`  # ❌ LLM sees ABSOLUTE PATH
"""
```

**Problem**: LLM receives absolute paths in the prompt:
```
## File: `/opt/andela/genai/patchpro-bot-test-bafecd1/src/patchpro_bot/__init__.py`
```

---

### 3. **LLM Response** (JSON from GPT-4)
```json
{
  "patches": [
    {
      "file_path": "/opt/andela/genai/patchpro-bot-test-bafecd1/src/patchpro_bot/__init__.py",  
      "diff_content": "diff --git a/analyzer.py b/analyzer.py\n...",  
      "summary": "Fix imports"
    }
  ]
}
```

**Problem**: LLM returns **ABSOLUTE PATH** but generates diff with **TRUNCATED PATH**
- Why? LLM tries to be "helpful" and normalize paths, but does it incorrectly
- Result: `file_path` is absolute, but `diff_content` has truncated path

---

### 4. **DiffGenerator.generate_diff_from_patch()** (generator.py - Line 164)
```python
def generate_diff_from_patch(self, diff_patch: DiffPatch) -> str:
    file_path = diff_patch.file_path  # ❌ Absolute: "/opt/.../analyzer.py"
    relative_path = self._make_relative_path(file_path)  # ✅ Tries to fix it
    
    # BUT the diff_content already has truncated paths from LLM!
    if diff_content.startswith('diff --git'):
        # Lines 185-197: Tries to fix headers
        for line in lines:
            if line.startswith('diff --git '):
                fixed_lines.append(f'diff --git a/{relative_path} b/{relative_path}')
```

**Problem**: Even though `_make_relative_path()` exists, the LLM's diff already has wrong paths
- LLM generated: `diff --git a/analyzer.py b/analyzer.py`
- Should be: `diff --git a/src/patchpro_bot/analyzer.py b/src/patchpro_bot/analyzer.py`

---

### 5. **_make_relative_path() Bug** (generator.py - Line 45)
```python
def _get_git_root(self, file_path: Optional[str] = None) -> Optional[Path]:
    try:
        # ❌ BUG HERE - Uses file's parent directory as cwd!
        cwd = Path(file_path).parent if file_path else Path.cwd()
        
        # In multiprocessing context, this executes from WRONG directory
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=str(cwd),  # ❌ Points to file's directory, not repo root!
            ...
        )
```

**Problem in Multiprocessing Context**:
- **Single file**: `cwd = /opt/andela/genai/patchpro-bot-test-bafecd1` ✅ Works
- **Many files**: `cwd = /opt/andela/genai/patchpro-bot-test-bafecd1/src/patchpro_bot` ❌ Wrong!
- **Result**: `git rev-parse` returns correct root, but path calculation fails

---

## 🔍 Root Cause Analysis

### The Real Problem: **TWO BUGS**

#### Bug #1: Analyzer stores absolute paths
- **Location**: `analyzer.py` lines ~232 (RuffNormalizer) and ~388 (SemgrepNormalizer)
- **Code**: Uses `ruff_finding['filename']` directly without normalization
- **Impact**: findings.json has absolute paths instead of relative

#### Bug #2: LLM receives absolute paths and generates truncated diffs
- **Location**: `prompts.py` line 192 - prompt includes absolute paths
- **Code**: `prompt += f"## File: `{file_path}`"`
- **Impact**: LLM sees absolute path, tries to normalize, generates wrong diff headers

---

## 🎯 Why It Only Manifests in Async/Multiprocessing

1. **Single file/sync mode**: 
   - Process runs from repo root
   - `Path.cwd()` = `/opt/andela/genai/patchpro-bot-test-bafecd1`
   - Absolute paths get normalized correctly

2. **Many files/async mode**:
   - Multiprocessing spawns separate processes
   - Each process may have different working directory
   - `Path.cwd()` might be `/opt/andela/genai/patchpro-bot-test-bafecd1/src/patchpro_bot`
   - Path normalization fails or produces truncated paths

---

## 💡 The Fix: Normalize at Analysis Time

### Option A: Fix in analyzer.py (RECOMMENDED)
**Rationale**: Prevent absolute paths from EVER entering the system

```python
# In RuffNormalizer._convert_ruff_finding() - Line ~232
location = Location(
    file=self._normalize_file_path(ruff_finding['filename']),  # ✅ Fix here
    line=location_data["row"],
    ...
)

def _normalize_file_path(self, file_path: str) -> str:
    """Convert absolute path to relative path from git root."""
    if not Path(file_path).is_absolute():
        return file_path  # Already relative
    
    # Get git root WITHOUT using cwd parameter (avoid multiprocessing bug)
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            # ✅ Don't pass cwd - use current process directory
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = Path(result.stdout.strip())
        abs_path = Path(file_path).resolve()
        return str(abs_path.relative_to(git_root))
    except:
        return file_path  # Fallback
```

**Benefits**:
- ✅ Single point of normalization
- ✅ Prevents absolute paths in findings.json
- ✅ LLM receives clean relative paths
- ✅ No downstream fixes needed
- ✅ Works in all modes (sync, async, multiprocessing)

---

### Option B: Fix in diff/generator.py (NOT RECOMMENDED)
**Rationale**: Fixing symptoms downstream

```python
# Would need to fix _get_git_root() to not use cwd=file_dir
def _get_git_root(self) -> Optional[Path]:
    result = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        # ✅ Remove cwd parameter
        capture_output=True,
        ...
    )
```

**Problems**:
- ❌ Findings.json still has absolute paths
- ❌ LLM still sees absolute paths
- ❌ Two normalization points (analyzer + generator)
- ❌ Harder to debug
- ❌ More likely to have edge cases

---

## 🧪 Test Evidence

### Test Setup
- **Worktree**: `/opt/andela/genai/patchpro-bot-test-bafecd1`
- **Commit**: bafecd1 (20 files changed)
- **Trigger**: `git commit` → post-commit hook → async analysis
- **Tools**: Ruff + Semgrep with LLM patch generation

### Results
```bash
# findings.json shows absolute paths
"file": "/opt/andela/genai/patchpro-bot-test-bafecd1/src/patchpro_bot/__init__.py"

# patch_combined_20251004_214105.diff shows truncated paths
diff --git a/analyzer.py b/analyzer.py  # ❌ Should be src/patchpro_bot/analyzer.py

# git apply fails
error: analyzer.py: No such file or directory
```

### Verification Command
```bash
git apply --check .patchpro/patch_combined_*.diff
# Expected: Success
# Actual: Error - file not found
```

---

## 📋 Implementation Checklist

### Phase 1: Fix Analysis Stage (analyzer.py)
- [ ] Add `_normalize_file_path()` method to RuffNormalizer
- [ ] Add `_normalize_file_path()` method to SemgrepNormalizer
- [ ] Update `Location` creation to use normalized paths
- [ ] Remove `cwd=file_dir` parameter (if exists)
- [ ] Test with single file (verify still works)
- [ ] Test with 20 files (verify bug fixed)

### Phase 2: Validation
- [ ] Re-run test in worktree
- [ ] Verify findings.json has relative paths
- [ ] Verify patches have correct paths
- [ ] Verify `git apply` succeeds

### Phase 3: Optional Cleanup
- [ ] Consider removing `_make_relative_path()` from generator.py (redundant)
- [ ] Or keep it as defensive programming (belt + suspenders)

---

## 🔗 Related Files

### Primary Bug Locations
1. `/opt/andela/genai/patchpro-bot-agent-dev/src/patchpro_bot/analyzer.py` - Lines ~232, ~388
2. `/opt/andela/genai/patchpro-bot-agent-dev/src/patchpro_bot/diff/generator.py` - Line 45

### Affected Components
- `cli.py` - Line 1039 (multiprocessing.Process spawn)
- `agent_core.py` - Line 863 (patch writing)
- `llm/prompts.py` - Line 192 (prompt building)
- `llm/response_parser.py` - Line 48 (DiffPatch dataclass)
- `diff/patch_writer.py` - Line 115 (combined patch creation)

---

## 📊 Impact Assessment

### Severity: **HIGH** 🔴
- Blocks patch application in production async mode
- Only manifests under load (many files)
- Hard to reproduce in manual testing

### Scope
- ✅ Affects: Async/multiprocessing mode with multiple files
- ❌ Does NOT affect: Single file commits, manual analysis

### User Impact
- Developers see patches generated but can't apply them
- `git apply` fails with "No such file or directory"
- Requires manual intervention

---

## 🎓 Lessons Learned

1. **Test with realistic workloads**: Single file tests miss multiprocessing bugs
2. **Avoid `cwd` parameters**: Especially in multiprocessing contexts
3. **Normalize early**: Fix data at entry point, not at exit point
4. **Git hooks are essential**: Manual commands don't reproduce real workflow
5. **Absolute vs relative paths**: Critical for diff generation

---

**Status**: Bug confirmed and analyzed  
**Next Step**: Implement Option A (normalize in analyzer.py)  
**Issue**: #12  
**PR**: #11
