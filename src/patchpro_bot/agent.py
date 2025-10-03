"""
Agent Core module for generating code fixes using LLM (OpenAI).
Consumes normalized findings and produces structured markdown with diffs.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .analyzer import NormalizedFindings, Finding


class ModelProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    # Future: ANTHROPIC, LOCAL, etc.


@dataclass
class AgentConfig:
    """Configuration for the agent."""
    provider: ModelProvider = ModelProvider.OPENAI
    model: str = "gpt-4o-mini"  # Cost-effective choice
    api_key: Optional[str] = None
    max_tokens: int = 2000
    temperature: float = 0.1  # Low temperature for deterministic fixes
    max_findings_per_request: int = 5  # Process in batches
    max_lines_per_diff: int = 50  # Guardrail: max lines in a single diff
    include_explanation: bool = True
    timeout: int = 30  # seconds
    
    def __post_init__(self):
        """Validate and set defaults from environment."""
        if self.api_key is None:
            self.api_key = os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key and self.provider == ModelProvider.OPENAI:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key to AgentConfig."
            )


@dataclass
class GeneratedFix:
    """A single generated fix with diff and explanation."""
    finding_id: str
    file_path: str
    original_code: str
    fixed_code: str
    explanation: str
    diff: str
    confidence: str = "medium"  # low, medium, high


@dataclass
class AgentResult:
    """Result from agent processing."""
    fixes: List[GeneratedFix]
    summary: str
    total_findings: int
    fixes_generated: int
    skipped: int
    errors: List[str]


class PromptBuilder:
    """Builds prompts for the LLM based on findings."""
    
    SYSTEM_PROMPT = """You are PatchPro, an expert code repair assistant. Your role is to:
1. Analyze code quality issues from static analysis tools (Ruff, Semgrep)
2. Generate minimal, focused diffs that fix the issues
3. Provide clear explanations for each fix

Guidelines:
- Generate ONLY the minimal diff needed to fix the issue
- Keep changes focused and atomic (one issue at a time)
- Preserve code style and formatting
- Include brief explanations for each change
- If a fix is unsafe or unclear, skip it and explain why
- Use unified diff format for patches

Output format must be valid JSON with this structure:
{
  "fixes": [
    {
      "finding_id": "abc123",
      "file_path": "path/to/file.py",
      "original_code": "import os, sys",
      "fixed_code": "import os\\nimport sys",
      "explanation": "Split multiple imports on one line into separate lines per PEP 8",
      "confidence": "high"
    }
  ]
}"""

    @staticmethod
    def build_fix_prompt(findings: List[Finding], file_contents: Dict[str, str]) -> str:
        """Build prompt for generating fixes."""
        findings_data = []
        
        for finding in findings:
            # Extract relevant code snippet
            file_path = finding.location.file
            if file_path in file_contents:
                lines = file_contents[file_path].split('\n')
                start_line = max(0, finding.location.line - 3)  # 2 lines context before
                end_line = min(len(lines), finding.location.line + 3)  # 2 lines context after
                code_snippet = '\n'.join(lines[start_line:end_line])
                
                findings_data.append({
                    "id": finding.id,
                    "file": file_path,
                    "line": finding.location.line,
                    "rule": finding.rule_id,
                    "message": finding.message,
                    "severity": finding.severity,
                    "category": finding.category,
                    "code_snippet": code_snippet,
                    "has_suggestion": finding.suggestion is not None
                })
        
        prompt = f"""Analyze these {len(findings_data)} code issues and generate fixes:

{json.dumps(findings_data, indent=2)}

For each issue:
1. Identify the problematic code
2. Generate the corrected code
3. Provide a brief explanation
4. Assess your confidence level (low/medium/high)

Return your response as valid JSON following the specified format.
If you cannot safely fix an issue, omit it from the fixes array."""

        return prompt


class LLMClient:
    """Wrapper for LLM API calls."""
    
    def __init__(self, config: AgentConfig):
        """Initialize LLM client."""
        self.config = config
        
        if config.provider == ModelProvider.OPENAI:
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    "OpenAI package not installed. Install with: pip install openai"
                )
            self.client = OpenAI(api_key=config.api_key, timeout=config.timeout)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")
    
    def generate_fixes(
        self,
        findings: List[Finding],
        file_contents: Dict[str, str]
    ) -> Tuple[List[GeneratedFix], List[str]]:
        """Generate fixes for findings using LLM."""
        if not findings:
            return [], []
        
        prompt = PromptBuilder.build_fix_prompt(findings, file_contents)
        fixes = []
        errors = []
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": PromptBuilder.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                response_format={"type": "json_object"}  # Enforce JSON response
            )
            
            # Parse response
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Convert to GeneratedFix objects
            for fix_data in result.get("fixes", []):
                try:
                    # Generate unified diff
                    diff = self._generate_diff(
                        fix_data["file_path"],
                        fix_data["original_code"],
                        fix_data["fixed_code"]
                    )
                    
                    # Validate diff size
                    diff_lines = diff.count('\n')
                    if diff_lines > self.config.max_lines_per_diff:
                        errors.append(
                            f"Skipped fix for {fix_data['finding_id']}: "
                            f"diff too large ({diff_lines} lines)"
                        )
                        continue
                    
                    fix = GeneratedFix(
                        finding_id=fix_data["finding_id"],
                        file_path=fix_data["file_path"],
                        original_code=fix_data["original_code"],
                        fixed_code=fix_data["fixed_code"],
                        explanation=fix_data["explanation"],
                        diff=diff,
                        confidence=fix_data.get("confidence", "medium")
                    )
                    fixes.append(fix)
                
                except (KeyError, ValueError) as e:
                    errors.append(f"Failed to parse fix: {e}")
        
        except Exception as e:
            errors.append(f"LLM API error: {str(e)}")
        
        return fixes, errors
    
    def _generate_diff(self, file_path: str, original: str, fixed: str) -> str:
        """Generate unified diff format."""
        import difflib
        
        original_lines = original.splitlines(keepends=True)
        fixed_lines = fixed.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            fixed_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=''
        )
        
        return ''.join(diff)


class PatchProAgent:
    """Main agent for generating code fixes."""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize agent."""
        self.config = config or AgentConfig()
        self.llm_client = LLMClient(self.config)
    
    def process_findings(
        self,
        findings: NormalizedFindings,
        source_files: Dict[str, str]
    ) -> AgentResult:
        """
        Process findings and generate fixes.
        
        Args:
            findings: Normalized findings from analyzer
            source_files: Dictionary mapping file paths to their contents
        
        Returns:
            AgentResult with generated fixes and metadata
        """
        all_fixes = []
        all_errors = []
        
        # Filter findings that are fixable
        fixable_findings = [
            f for f in findings.findings
            if f.category in ["style", "import", "correctness"]
            and f.severity in ["error", "warning"]
        ]
        
        # Process in batches
        batch_size = self.config.max_findings_per_request
        for i in range(0, len(fixable_findings), batch_size):
            batch = fixable_findings[i:i + batch_size]
            
            fixes, errors = self.llm_client.generate_fixes(batch, source_files)
            all_fixes.extend(fixes)
            all_errors.extend(errors)
        
        # Generate summary
        summary = self._generate_summary(findings, all_fixes, all_errors)
        
        return AgentResult(
            fixes=all_fixes,
            summary=summary,
            total_findings=len(findings.findings),
            fixes_generated=len(all_fixes),
            skipped=len(fixable_findings) - len(all_fixes),
            errors=all_errors
        )
    
    def _generate_summary(
        self,
        findings: NormalizedFindings,
        fixes: List[GeneratedFix],
        errors: List[str]
    ) -> str:
        """Generate summary of the analysis and fixes."""
        summary_lines = [
            f"## PatchPro Analysis Summary",
            f"",
            f"- **Total Findings:** {len(findings.findings)}",
            f"- **Fixes Generated:** {len(fixes)}",
            f"- **Analysis Tool:** {findings.metadata.tool}",
            f"- **Timestamp:** {findings.metadata.timestamp}",
        ]
        
        if errors:
            summary_lines.extend([
                f"",
                f"### ⚠️ Warnings",
                *[f"- {error}" for error in errors[:5]]  # Show first 5
            ])
        
        return "\n".join(summary_lines)
    
    def generate_markdown_report(self, result: AgentResult) -> str:
        """
        Generate markdown report for PR comment.
        
        Args:
            result: Agent processing result
        
        Returns:
            Formatted markdown string
        """
        lines = [
            "# 🔧 PatchPro Code Fixes",
            "",
            result.summary,
            "",
        ]
        
        if not result.fixes:
            lines.extend([
                "## No Automated Fixes Available",
                "",
                "While issues were detected, PatchPro couldn't generate safe automated fixes.",
                "Please review the findings manually.",
            ])
            return "\n".join(lines)
        
        lines.extend([
            "## 📝 Proposed Fixes",
            "",
        ])
        
        # Group fixes by file
        fixes_by_file = {}
        for fix in result.fixes:
            if fix.file_path not in fixes_by_file:
                fixes_by_file[fix.file_path] = []
            fixes_by_file[fix.file_path].append(fix)
        
        # Generate fix sections
        for file_path, file_fixes in fixes_by_file.items():
            lines.extend([
                f"### 📄 `{file_path}`",
                "",
            ])
            
            for idx, fix in enumerate(file_fixes, 1):
                confidence_emoji = {
                    "high": "✅",
                    "medium": "⚠️",
                    "low": "❓"
                }.get(fix.confidence, "⚠️")
                
                lines.extend([
                    f"#### Fix {idx}: {confidence_emoji} {fix.explanation}",
                    "",
                    "**Diff:**",
                    "```diff",
                    fix.diff,
                    "```",
                    "",
                ])
        
        lines.extend([
            "---",
            "",
            "*Generated by PatchPro AI Code Repair Assistant*",
            "*Review all changes before applying*",
        ])
        
        return "\n".join(lines)


def load_source_files(findings: NormalizedFindings, base_path: Path) -> Dict[str, str]:
    """
    Load source files referenced in findings.
    
    Args:
        findings: Normalized findings
        base_path: Base directory for resolving file paths
    
    Returns:
        Dictionary mapping file paths to their contents
    """
    source_files = {}
    unique_files = set(f.location.file for f in findings.findings)
    
    for file_path in unique_files:
        try:
            # Try to resolve the path
            full_path = base_path / file_path
            if not full_path.exists():
                # Try relative to current directory
                full_path = Path(file_path)
            
            if full_path.exists() and full_path.is_file():
                source_files[file_path] = full_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Warning: Could not load {file_path}: {e}")
    
    return source_files
