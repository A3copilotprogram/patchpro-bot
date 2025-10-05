"""Prompt templates and builders for LLM interactions."""

import logging
from typing import List, Optional, Dict
from pathlib import Path

from ..analysis import FindingAggregator
from ..models import AnalysisFinding
from ..context_reader import FindingContextReader


logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds prompts for LLM interactions."""
    
    def __init__(self):
        """Initialize the prompt builder."""
        self.system_prompt = self.get_system_prompt()
    
    def build_code_fix_prompt(
        self,
        aggregator: FindingAggregator,
        max_findings: int = 10,
        include_context: bool = True,
        file_reader=None,
    ) -> str:
        """Build prompt for generating code fixes.
        
        Args:
            aggregator: Aggregated analysis findings
            max_findings: Maximum number of findings to include
            include_context: Whether to include code context
            file_reader: Optional file reader to get actual file content
            
        Returns:
            Formatted prompt string
        """
        # TODO: Update this function to deal with max findings
        # Limit and prioritize findings
        limited_aggregator = (
            aggregator
            .deduplicate()
            .sort_by_priority()
            .limit_findings(max_findings)
        )
        
        findings_context = limited_aggregator.to_prompt_context(
            include_code_snippets=include_context
        )
        
        # Only include file contents for files that had failed matches previously
        # This preserves the existing good behavior while fixing the example.py issue
        file_contents = {}
        if file_reader and limited_aggregator.findings:
            # Include file content for all files with findings to ensure accurate fixes
            files_with_findings = set()
            for finding in limited_aggregator.findings:
                files_with_findings.add(finding.location.file)
            
            for file_path in files_with_findings:
                try:
                    content = file_reader.read_file(file_path)
                    if content:
                        file_contents[file_path] = content
                except Exception as e:
                    logger.warning(f"Could not read file {file_path}: {e}")
        
        # Build the main prompt
        prompt = f"""I need your help to fix code issues found by static analysis tools (Ruff and Semgrep).

{findings_context}"""

        # Add file contents only for problematic files
        if file_contents:
            prompt += "\n\nFor files where the analysis findings may not show the complete context, here is the actual content:\n"
            for file_path, content in file_contents.items():
                prompt += f"\n### {file_path}\n```python\n{content}\n```\n"

        prompt += """

Please provide specific code fixes for these issues. Return your response as a valid JSON object with the following structure:

{
  "fixes": [
    {
      "fix_number": 1,
      "description": "Brief description of the fix",
      "file_path": "path/to/file.py",
      "lines": "X-Y",
      "issue": "Description of the problem",
      "original_code": "Original problematic code (use EXACTLY what appears in the findings/analysis)",
      "fixed_code": "Fixed code",
      "rationale": "Explanation of why this fix works"
    }
  ]
}

Focus on:
- Security vulnerabilities (highest priority)
- Bugs and errors that could cause runtime issues
- Code style issues that affect readability
- Performance improvements where applicable

IMPORTANT: 
- For the original_code field, use EXACTLY what appears in the file content provided above, not what's shown in the analysis findings
- If file content is provided above, use that as the source of truth for the exact code snippets
- Generate minimal, focused fixes that address the specific issues without making unnecessary changes to unrelated code
- Ensure the original_code matches EXACTLY what exists in the file (including indentation and spacing)
- Return only valid JSON, no additional text or formatting
"""
        
        return prompt
    
    def build_diff_generation_prompt(
        self,
        file_path: str,
        original_content: str,
        issue_description: str,
        suggested_fix: Optional[str] = None,
    ) -> str:
        """Build prompt for generating unified diff.
        
        Args:
            file_path: Path to the file being fixed
            original_content: Original file content
            issue_description: Description of the issue to fix
            suggested_fix: Optional suggested fix
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""I need you to generate a unified diff patch for a code fix.

**File**: `{file_path}`
**Issue**: {issue_description}

**Original File Content**:
```python
{original_content}
```
"""

        if suggested_fix:
            prompt += f"""
**Suggested Fix**: {suggested_fix}
"""

        prompt += """
Please provide a unified diff patch that fixes this issue. Return your response as a valid JSON object with the following structure:

{
  "patch": {
    "file_path": "path/to/file.py",
    "diff_content": "unified diff content starting with 'diff --git'",
    "summary": "Brief description of changes made"
  }
}

Requirements:
- Use standard unified diff format (diff -u)
- Include appropriate context lines (usually 3-5 lines before/after changes)
- Make minimal changes that address only the specific issue
- Ensure the fix follows Python best practices
- Preserve existing code style and formatting where possible

Return only valid JSON, no additional text or formatting.
"""
        
        return prompt
    
    def build_batch_diff_prompt(
        self,
        file_fixes: Dict[str, List[AnalysisFinding]],
        file_contents: Dict[str, str],
    ) -> str:
        """Build prompt for generating multiple diffs in batch.
        
        Args:
            file_fixes: Dictionary mapping file paths to their findings
            file_contents: Dictionary mapping file paths to their content
            
        Returns:
            Formatted prompt string
        """
        prompt = """I need you to generate unified diff patches for multiple files with code issues.

Files to fix:
"""
        
        for file_path, findings in file_fixes.items():
            content = file_contents.get(file_path, "")
            
            # DEBUG: Log the file path being sent to LLM
            logger.warning(f"DEBUG: Sending to LLM - file_path={file_path}")
            
            prompt += f"""
## File: `{file_path}`

**Issues found**:
"""
            
            for i, finding in enumerate(findings, 1):
                prompt += f"""
{i}. **{finding.rule_id}** (Line {finding.location.line})
   - {finding.message}
"""
                if finding.suggested_fix:
                    prompt += f"   - Suggested fix: {finding.suggested_fix}\n"
            
            prompt += f"""
**File Content**:
```python
{content}
```

---
"""
        
        prompt += """
Please generate unified diff patches for each file that fix all the identified issues. Return your response as a valid JSON object with the following structure:

{
  "patches": [
    {
      "file_path": "path/to/file.py",
      "diff_content": "unified diff content starting with 'diff --git'",
      "summary": "Brief description of changes made"
    }
  ]
}

Requirements:
- Generate a separate diff for each file
- Use standard unified diff format
- Include context lines (3-5 lines before/after changes)
- Make minimal, targeted fixes
- Preserve existing code style
- Address all issues in each file

Return only valid JSON, no additional text or formatting.
"""
        
        return prompt
    
    def build_unified_diff_prompt_with_context(
        self,
        file_fixes: Dict[str, List[AnalysisFinding]],
        repo_path: str,
    ) -> str:
        """Build prompt using real file context for unified diff generation.
        
        Uses FindingContextReader to get actual code around findings.
        This is the NEW golden approach that prevents LLM hallucination.
        
        Args:
            file_fixes: Dictionary mapping file paths to their findings
            repo_path: Path to git repository root
            
        Returns:
            Formatted prompt string
        """
        context_reader = FindingContextReader(context_lines=5)
        
        prompt = """I need you to generate unified diff patches for code issues found by static analysis.

IMPORTANT INSTRUCTIONS:
1. You will receive ACTUAL file content with line numbers
2. The problematic lines are marked with → arrows
3. Generate standard unified diff format (diff --git, ---, +++, @@)
4. Use EXACTLY the line numbers and content shown below
5. Make minimal, focused changes to fix the issues
6. Preserve indentation, spacing, and style

Files to fix:
"""
        
        for file_path, findings in file_fixes.items():
            prompt += f"\n## File: `{file_path}`\n\n**Issues found**:\n"
            
            for i, finding in enumerate(findings, 1):
                prompt += f"{i}. **{finding.rule_id}** at line {finding.location.line}\n"
                prompt += f"   - {finding.message}\n"
                if finding.suggested_fix:
                    prompt += f"   - Suggested fix: {finding.suggested_fix}\n"
            
            # Get real code context for each finding
            prompt += "\n**Actual Code Context** (→ marks problematic lines):\n```python\n"
            
            # Get unique line ranges to avoid duplicates
            line_ranges = set()
            for finding in findings:
                start_line = finding.location.line
                end_line = finding.location.end_line or start_line
                line_ranges.add((start_line, end_line))
            
            # Get context for each range
            contexts = []
            for start, end in sorted(line_ranges):
                full_path = Path(repo_path) / file_path
                context = context_reader.get_code_context(str(full_path), start, end)
                if context:
                    contexts.append(context)
            
            # Combine contexts
            if contexts:
                prompt += "\n\n".join(contexts)
            else:
                # Fallback: show full file if context extraction fails
                try:
                    full_path = Path(repo_path) / file_path
                    full_content = context_reader.get_full_file_content(str(full_path))
                    if full_content:
                        prompt += full_content
                except Exception as e:
                    logger.error(f"Failed to read {file_path}: {e}")
                    prompt += f"# ERROR: Could not read file content\n"
            
            prompt += "\n```\n\n---\n"
        
        prompt += """
Please generate unified diff patches for each file. Return your response as valid JSON:

{
  "patches": [
    {
      "file_path": "relative/path/to/file.py",
      "diff_content": "diff --git a/file.py b/file.py\\nindex abc123..def456 100644\\n--- a/file.py\\n+++ b/file.py\\n@@ -10,7 +10,7 @@\\n context line\\n-old line\\n+new line\\n context line",
      "summary": "Fix: Brief description of what was changed"
    }
  ]
}

UNIFIED DIFF FORMAT REQUIREMENTS:
- Start with: diff --git a/{file} b/{file}
- Include: --- a/{file} and +++ b/{file}
- Hunk header: @@ -old_start,old_count +new_start,new_count @@
- Include 3-5 context lines before and after changes
- Use - for removed lines, + for added lines
- Space prefix for context lines

CRITICAL PATH REQUIREMENTS:
- Use RELATIVE paths from repository root (e.g., src/module/file.py)
- NEVER use absolute paths (e.g., /opt/andela/genai/repo/src/module/file.py)
- File paths in diff headers should match the file_path field
- Example: if file_path is "src/app.py", use:
  diff --git a/src/app.py b/src/app.py
  --- a/src/app.py
  +++ b/src/app.py

CRITICAL CODE REQUIREMENTS:
- Use the EXACT line numbers shown in the code context above
- Match indentation and spacing exactly
- Make minimal changes - only fix the reported issues
- Ensure patches can be applied with `git apply`

Return ONLY valid JSON, no additional text."""
        
        return prompt
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for LLM interactions.
        
        Returns:
            System prompt string
        """
        return """You are an expert Python developer and code reviewer specializing in generating unified diff patches.

Your expertise includes:
- Understanding Ruff (Python linter) and Semgrep (static analysis) outputs
- Generating precise, minimal unified diff patches
- Following standard unified diff format (diff -u)
- Using exact line numbers and code from provided context
- Following Python best practices and PEP standards
- Security-aware coding practices

CRITICAL GUIDELINES:
1. Always use EXACT code from the provided file context - never hallucinate or guess
2. Generate proper unified diff format with ---, +++, and @@ headers
3. Include 3-5 context lines before and after changes
4. Make minimal changes that address only the specific issues
5. Preserve existing code style, indentation, and formatting
6. Always prioritize security fixes over style issues
7. Always respond with valid JSON format as requested
8. Never include additional text outside the requested JSON structure

UNIFIED DIFF FORMAT:
```
diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -line_num,count +line_num,count @@
 context line
-removed line
+added line
 context line
```

Be precise, thorough, and security-conscious in your responses. Always return properly formatted JSON."""
