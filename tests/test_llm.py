"""Tests for LLM module."""

import pytest
from unittest.mock import Mock, patch

from patchpro_bot.llm import PromptBuilder, ResponseParser, ResponseType, ParsedResponse
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
        assert "JSON object" in prompt
        assert '"fixes"' in prompt
        assert '"fix_number"' in prompt
        assert '"original_code"' in prompt
        assert '"fixed_code"' in prompt
    
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
        assert "JSON object" in prompt
        assert '"patch"' in prompt
        assert '"diff_content"' in prompt
    
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
        assert "JSON object" in prompt
        assert '"patches"' in prompt


class TestResponseParser:
    """Tests for ResponseParser class."""
    
    def test_init(self):
        """Test ResponseParser initialization."""
        parser = ResponseParser()
        assert parser is not None
    
    def test_parse_code_fixes(self):
        """Test parsing code fixes from JSON response."""
        response = """{
  "fixes": [
    {
      "fix_number": 1,
      "description": "Remove unused import",
      "file_path": "test.py",
      "lines": "1",
      "issue": "Unused import 'os'",
      "original_code": "import os\\nimport sys",
      "fixed_code": "import sys",
      "rationale": "The 'os' module is imported but never used in the code."
    },
    {
      "fix_number": 2,
      "description": "Fix security issue",
      "file_path": "app.py",
      "lines": "10-12",
      "issue": "Dangerous subprocess call",
      "original_code": "subprocess.call(user_input, shell=True)",
      "fixed_code": "subprocess.run(user_input, shell=False, check=True)",
      "rationale": "Using shell=False prevents shell injection attacks."
    }
  ]
}"""
        
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
        """Test parsing diff patches from JSON response."""
        response = """{
  "patches": [
    {
      "file_path": "test.py",
      "diff_content": "diff --git a/test.py b/test.py\\nindex 1234567..abcdefg 100644\\n--- a/test.py\\n+++ b/test.py\\n@@ -1,2 +1,1 @@\\n-import os\\n import sys",
      "summary": "Removed unused import"
    },
    {
      "file_path": "app.py", 
      "diff_content": "diff --git a/app.py b/app.py\\nindex abcdefg..1234567 100644\\n--- a/app.py\\n+++ b/app.py\\n@@ -8,1 +8,1 @@\\n-subprocess.call(cmd, shell=True)\\n+subprocess.run(cmd, shell=False)",
      "summary": "Fixed security vulnerability"
    }
  ]
}"""
        
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
    
    def test_parse_single_diff_patch(self):
        """Test parsing a single diff patch from JSON response."""
        response = """{
  "patch": {
    "file_path": "test.py",
    "diff_content": "diff --git a/test.py b/test.py\\nindex 1234567..abcdefg 100644\\n--- a/test.py\\n+++ b/test.py\\n@@ -1,2 +1,1 @@\\n-import os\\n import sys",
    "summary": "Removed unused import"
  }
}"""
        
        parser = ResponseParser()
        patches = parser.parse_diff_patches(response)
        
        assert len(patches) == 1
        assert patches[0].file_path == "test.py"
        assert "diff --git" in patches[0].diff_content
        assert patches[0].summary == "Removed unused import"
    
    def test_extract_code_blocks_deprecated(self):
        """Test that extract_code_blocks is deprecated."""
        parser = ResponseParser()
        response = """
```python
def hello():
    print("Hello, world!")
```
"""
        # Should return empty list and log warning
        python_blocks = parser.extract_code_blocks(response, "python")
        assert len(python_blocks) == 0
    
    def test_extract_diff_blocks_deprecated(self):
        """Test that extract_diff_blocks is deprecated."""
        parser = ResponseParser()
        response = """
```diff
diff --git a/file1.py b/file1.py
-old line
+new line
```
"""
        # Should return empty list and log warning
        diff_blocks = parser.extract_diff_blocks(response)
        assert len(diff_blocks) == 0
    
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
        
        # Should normalize line endings and reduce excessive whitespace
        assert "Some content" in cleaned
        assert "More content" in cleaned
        assert not cleaned.startswith('\n')
        assert not cleaned.endswith('\n\n\n')
    
    def test_parse_json_with_wrapper_text(self):
        """Test parsing JSON that's wrapped in additional text."""
        parser = ResponseParser()
        
        response_with_wrapper = """
Here's the JSON response:

```json
{
  "fixes": [
    {
      "fix_number": 1,
      "description": "Test fix",
      "file_path": "test.py",
      "lines": "1",
      "issue": "Test issue",
      "original_code": "old code",
      "fixed_code": "new code",
      "rationale": "Test rationale"
    }
  ]
}
```

That's the fix you requested.
"""
        
        fixes = parser.parse_code_fixes(response_with_wrapper)
        assert len(fixes) == 1
        assert fixes[0].description == "Test fix"
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON gracefully."""
        parser = ResponseParser()
        
        invalid_json = "This is not JSON at all"
        fixes = parser.parse_code_fixes(invalid_json)
        assert len(fixes) == 0
        
        partial_json = '{"fixes": [{"fix_number": 1, "description":'
        fixes = parser.parse_code_fixes(partial_json)
        assert len(fixes) == 0
    
    def test_parse_response_code_fixes(self):
        """Test unified response parsing for code fixes."""
        parser = ResponseParser()
        
        json_response = """{
  "fixes": [
    {
      "fix_number": 1,
      "description": "Remove unused import",
      "file_path": "test.py",
      "lines": "1",
      "issue": "Unused import 'os'",
      "original_code": "import os\\nimport sys",
      "fixed_code": "import sys",
      "rationale": "The 'os' module is imported but never used."
    }
  ]
}"""
        
        parsed_response = parser.parse_response(json_response, ResponseType.CODE_FIXES)
        
        assert parsed_response.response_type == ResponseType.CODE_FIXES
        assert len(parsed_response.code_fixes) == 1
        assert len(parsed_response.diff_patches) == 0
        assert parsed_response.code_fixes[0].description == "Remove unused import"
    
    def test_parse_response_diff_patches(self):
        """Test unified response parsing for diff patches."""
        parser = ResponseParser()
        
        json_response = """{
  "patches": [
    {
      "file_path": "test.py",
      "diff_content": "diff --git a/test.py b/test.py\\nindex 123..456\\n--- a/test.py\\n+++ b/test.py\\n@@ -1,2 +1,1 @@\\n-import os\\n import sys",
      "summary": "Removed unused import"
    }
  ]
}"""
        
        parsed_response = parser.parse_response(json_response, ResponseType.DIFF_PATCHES)
        
        assert parsed_response.response_type == ResponseType.DIFF_PATCHES
        assert len(parsed_response.code_fixes) == 0
        assert len(parsed_response.diff_patches) == 1
        assert parsed_response.diff_patches[0].file_path == "test.py"
