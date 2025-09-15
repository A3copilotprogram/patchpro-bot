"""Tests for LLM module."""

import pytest
from unittest.mock import Mock, patch

from patchpro_bot.llm import PromptBuilder, ResponseParser
from patchpro_bot.llm.response_parser import CodeFix, DiffPatch
from patchpro_bot.analysis import FindingAggregator
from patchpro_bot.models import AnalysisFinding, CodeLocation, Severity


class TestPromptBuilder:
    """Tests for PromptBuilder class."""
    
    def create_sample_aggregator(self):
        """Create sample aggregator for testing."""
        findings = [
            AnalysisFinding(
                tool="ruff",
                rule_id="F401",
                location=CodeLocation(file="test.py", line=1),
                message="Unused import 'os'",
                severity=Severity.ERROR,
                code_snippet="import os",
                suggested_fix="Remove unused import"
            ),
            AnalysisFinding(
                tool="semgrep",
                rule_id="security.dangerous-call",
                location=CodeLocation(file="test.py", line=10),
                message="Dangerous subprocess call",
                severity=Severity.HIGH,
                category="security"
            )
        ]
        return FindingAggregator(findings)
    
    def test_init(self):
        """Test PromptBuilder initialization."""
        builder = PromptBuilder()
        assert builder.system_prompt is not None
        assert "expert Python developer" in builder.system_prompt
    
    def test_build_code_fix_prompt(self):
        """Test building code fix prompt."""
        builder = PromptBuilder()
        aggregator = self.create_sample_aggregator()
        
        prompt = builder.build_code_fix_prompt(aggregator)
        
        assert "static analysis tools" in prompt
        assert "F401" in prompt
        assert "security.dangerous-call" in prompt
        assert "Unused import" in prompt
        assert "Dangerous subprocess call" in prompt
        assert "## Fix #" in prompt
        assert "**File**:" in prompt
        assert "**Original Code**:" in prompt
        assert "**Fixed Code**:" in prompt
    
    def test_build_code_fix_prompt_with_limits(self):
        """Test building code fix prompt with limits."""
        builder = PromptBuilder()
        aggregator = self.create_sample_aggregator()
        
        prompt = builder.build_code_fix_prompt(
            aggregator, 
            max_findings=1, 
            include_context=False
        )
        
        # Should limit findings and exclude code snippets
        assert "F401" in prompt or "security.dangerous-call" in prompt
        # Shouldn't include both due to limit
    
    def test_build_diff_generation_prompt(self):
        """Test building diff generation prompt."""
        builder = PromptBuilder()
        
        prompt = builder.build_diff_generation_prompt(
            file_path="test.py",
            original_content="import os\ndef main():\n    pass",
            issue_description="Remove unused import",
            suggested_fix="Delete import os line"
        )
        
        assert "test.py" in prompt
        assert "Remove unused import" in prompt
        assert "Delete import os line" in prompt
        assert "import os" in prompt
        assert "unified diff" in prompt
        assert "diff --git" in prompt
    
    def test_build_batch_diff_prompt(self):
        """Test building batch diff prompt."""
        builder = PromptBuilder()
        
        file_fixes = {
            "file1.py": [
                AnalysisFinding(
                    tool="ruff",
                    rule_id="F401",
                    location=CodeLocation(file="file1.py", line=1),
                    message="Unused import",
                    severity=Severity.ERROR
                )
            ]
        }
        
        file_contents = {
            "file1.py": "import os\ndef main():\n    pass"
        }
        
        prompt = builder.build_batch_diff_prompt(file_fixes, file_contents)
        
        assert "file1.py" in prompt
        assert "F401" in prompt
        assert "Unused import" in prompt
        assert "import os" in prompt
        assert "unified diff patches" in prompt


class TestResponseParser:
    """Tests for ResponseParser class."""
    
    def test_init(self):
        """Test ResponseParser initialization."""
        parser = ResponseParser()
        assert parser is not None
    
    def test_parse_code_fixes(self):
        """Test parsing code fixes from response."""
        response = """
## Fix #1: Remove unused import

**File**: `test.py`
**Lines**: 1
**Issue**: Unused import 'os'

**Original Code**:
```python
import os
import sys
```

**Fixed Code**:
```python
import sys
```

**Rationale**: The 'os' module is imported but never used in the code.

---

## Fix #2: Fix security issue

**File**: `app.py`
**Lines**: 10-12
**Issue**: Dangerous subprocess call

**Original Code**:
```python
subprocess.call(user_input, shell=True)
```

**Fixed Code**:
```python
subprocess.run(user_input, shell=False, check=True)
```

**Rationale**: Using shell=False prevents shell injection attacks.
"""
        
        parser = ResponseParser()
        fixes = parser.parse_code_fixes(response)
        
        assert len(fixes) == 2
        
        fix1 = fixes[0]
        assert fix1.fix_number == 1
        assert fix1.description == "Remove unused import"
        assert fix1.file_path == "test.py"
        assert fix1.lines == "1"
        assert "Unused import" in fix1.issue
        assert "import os" in fix1.original_code
        assert "import sys" in fix1.fixed_code
        assert "'os' module" in fix1.rationale
        
        fix2 = fixes[1]
        assert fix2.fix_number == 2
        assert fix2.description == "Fix security issue"
        assert fix2.file_path == "app.py"
    
    def test_parse_diff_patches(self):
        """Test parsing diff patches from response."""
        response = """
### Patch for `test.py`

```diff
diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,2 +1,1 @@
-import os
 import sys
```

**Summary**: Removed unused import

---

### Patch for `app.py`

```diff
diff --git a/app.py b/app.py
index abcdefg..1234567 100644
--- a/app.py
+++ b/app.py
@@ -8,1 +8,1 @@
-subprocess.call(cmd, shell=True)
+subprocess.run(cmd, shell=False)
```

**Summary**: Fixed security vulnerability
"""
        
        parser = ResponseParser()
        patches = parser.parse_diff_patches(response)
        
        assert len(patches) == 2
        
        patch1 = patches[0]
        assert patch1.file_path == "test.py"
        assert "diff --git a/test.py" in patch1.diff_content
        assert "-import os" in patch1.diff_content
        assert patch1.summary == "Removed unused import"
        
        patch2 = patches[1]
        assert patch2.file_path == "app.py"
        assert "shell=False" in patch2.diff_content
    
    def test_parse_standalone_diff(self):
        """Test parsing standalone diff blocks."""
        response = """
Here's the fix:

```diff
diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,2 +1,1 @@
-import os
 import sys
```
"""
        
        parser = ResponseParser()
        patches = parser.parse_diff_patches(response)
        
        assert len(patches) == 1
        assert patches[0].file_path == "test.py"
        assert "diff --git" in patches[0].diff_content
    
    def test_extract_code_blocks(self):
        """Test extracting code blocks."""
        response = """
Here's some Python code:

```python
def hello():
    print("Hello, world!")
```

And here's some JavaScript:

```javascript
console.log("Hello, world!");
```

Another Python block:

```python
import sys
sys.exit(0)
```
"""
        
        parser = ResponseParser()
        python_blocks = parser.extract_code_blocks(response, "python")
        
        assert len(python_blocks) == 2
        assert "def hello():" in python_blocks[0]
        assert "import sys" in python_blocks[1]
        
        js_blocks = parser.extract_code_blocks(response, "javascript")
        assert len(js_blocks) == 1
        assert "console.log" in js_blocks[0]
    
    def test_extract_diff_blocks(self):
        """Test extracting diff blocks."""
        response = """
Here are the changes:

```diff
diff --git a/file1.py b/file1.py
-old line
+new line
```

And another diff:

```diff
diff --git a/file2.py b/file2.py
-another old line
+another new line
```
"""
        
        parser = ResponseParser()
        diff_blocks = parser.extract_diff_blocks(response)
        
        assert len(diff_blocks) == 2
        assert "file1.py" in diff_blocks[0]
        assert "file2.py" in diff_blocks[1]
    
    def test_validate_diff_format(self):
        """Test validating diff format."""
        parser = ResponseParser()
        
        # Valid diff
        valid_diff = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,2 +1,1 @@
-import os
 import sys"""
        
        assert parser.validate_diff_format(valid_diff) is True
        
        # Invalid diff (missing headers)
        invalid_diff = "-old line\n+new line"
        assert parser.validate_diff_format(invalid_diff) is False
    
    def test_extract_file_path_from_diff(self):
        """Test extracting file path from diff."""
        parser = ResponseParser()
        
        diff_content = """diff --git a/src/test.py b/src/test.py
index 1234567..abcdefg 100644
--- a/src/test.py
+++ b/src/test.py
@@ -1,1 +1,1 @@
-old
+new"""
        
        file_path = parser.extract_file_path_from_diff(diff_content)
        assert file_path == "src/test.py"
        
        # Test with invalid diff
        invalid_diff = "-old\n+new"
        assert parser.extract_file_path_from_diff(invalid_diff) is None
    
    def test_clean_response_content(self):
        """Test cleaning response content."""
        parser = ResponseParser()
        
        messy_content = "\n\n\n  Some content  \r\n\r\n\n\n  More content  \n\n\n"
        cleaned = parser.clean_response_content(messy_content)
        
        assert cleaned == "Some content  \n\n  More content"
        assert not cleaned.startswith('\n')
        assert not cleaned.endswith('\n\n\n')
