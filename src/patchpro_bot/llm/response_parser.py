"""Parser for LLM responses."""

import re
import logging
from typing import List, Dict, Optional, NamedTuple
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class CodeFix:
    """Represents a code fix from LLM response."""
    fix_number: int
    description: str
    file_path: str
    lines: str
    issue: str
    original_code: str
    fixed_code: str
    rationale: str


@dataclass
class DiffPatch:
    """Represents a unified diff patch."""
    file_path: str
    diff_content: str
    summary: Optional[str] = None


class ResponseParser:
    """Parses LLM responses to extract structured information."""
    
    def __init__(self):
        """Initialize the response parser."""
        pass
    
    def parse_code_fixes(self, response_content: str) -> List[CodeFix]:
        """Parse code fixes from LLM response.
        
        Args:
            response_content: Raw LLM response content
            
        Returns:
            List of parsed code fixes
        """
        fixes = []
        
        if not response_content or not response_content.strip():
            logger.warning("Empty response content provided")
            return fixes
        
        # Pattern to match fix sections - more flexible and case-insensitive
        fix_pattern = r'## [Ff]ix #(\d+):\s*(.+?)\s*\n\s*\n\s*\*\*[Ff]ile\*\*:\s*`(.+?)`\s*\n\s*\*\*[Ll]ines\*\*:\s*(.+?)\s*\n(?:\s*\*\*[Ii]ssue\*\*:\s*(.+?)\s*\n\s*\n)?\s*\*\*[Oo]riginal [Cc]ode\*\*:\s*\n\s*```(?:python|py)\s*\n(.*?)\n\s*```\s*\n\s*\n\s*\*\*[Ff]ixed [Cc]ode\*\*:\s*\n\s*```(?:python|py)\s*\n(.*?)\n\s*```(?:\s*\n\s*\n\s*\*\*[Rr]ationale\*\*:\s*(.+?))?(?=\n\s*---|$|\n\s*## [Ff]ix|\n\s*### [Pp]atch)'
        
        matches = re.finditer(fix_pattern, response_content, re.DOTALL)
        
        for match in matches:
            try:
                fix = CodeFix(
                    fix_number=int(match.group(1)),
                    description=match.group(2).strip(),
                    file_path=match.group(3).strip(),
                    lines=match.group(4).strip(),
                    issue=match.group(5).strip() if match.group(5) else "No issue specified",
                    original_code=match.group(6).strip(),
                    fixed_code=match.group(7).strip(),
                    rationale=match.group(8).strip() if match.group(8) else "No rationale provided",
                )
                fixes.append(fix)
                logger.debug(f"Parsed fix #{fix.fix_number} for {fix.file_path}")
            except Exception as e:
                logger.error(f"Failed to parse fix from match: {e}")
                continue
        
        logger.info(f"Parsed {len(fixes)} code fixes from response")
        return fixes
    
    def parse_diff_patches(self, response_content: str) -> List[DiffPatch]:
        """Parse unified diff patches from LLM response.
        
        Args:
            response_content: Raw LLM response content
            
        Returns:
            List of parsed diff patches
        """
        patches = []
        
        if not response_content or not response_content.strip():
            logger.warning("Empty response content provided")
            return patches
        
        # Pattern to match patch sections - more flexible and case-insensitive
        patch_pattern = r'### [Pp]atch for `(.+?)`\s*\n\s*\n\s*```diff\s*\n(.*?)\n\s*```(?:\s*\n\s*\n\s*\*\*[Ss]ummary\*\*:\s*(.+?))?(?=\n---|### [Pp]atch for|$)'
        
        matches = re.finditer(patch_pattern, response_content, re.DOTALL)
        
        for match in matches:
            try:
                patch = DiffPatch(
                    file_path=match.group(1).strip(),
                    diff_content=match.group(2).strip(),
                    summary=match.group(3).strip() if match.group(3) else None,
                )
                patches.append(patch)
                logger.debug(f"Parsed diff patch for {patch.file_path}")
            except Exception as e:
                logger.error(f"Failed to parse patch from match: {e}")
                continue
        
        # Also try to extract standalone diffs (without the ### Patch for format)
        standalone_diff_pattern = r'```diff\n(diff --git.*?)\n```'
        standalone_matches = re.finditer(standalone_diff_pattern, response_content, re.DOTALL)
        
        for match in standalone_matches:
            try:
                diff_content = match.group(1).strip()
                
                # Extract file path from diff header
                file_match = re.search(r'diff --git a/(.+?) b/', diff_content)
                if file_match:
                    file_path = file_match.group(1)
                    
                    # Check if we already have this patch
                    if not any(p.file_path == file_path for p in patches):
                        patch = DiffPatch(
                            file_path=file_path,
                            diff_content=diff_content,
                        )
                        patches.append(patch)
                        logger.debug(f"Parsed standalone diff patch for {patch.file_path}")
            except Exception as e:
                logger.error(f"Failed to parse standalone diff: {e}")
                continue
        
        logger.info(f"Parsed {len(patches)} diff patches from response")
        return patches
    
    def extract_code_blocks(self, response_content: str, language: str = "python") -> List[str]:
        """Extract code blocks from response.
        
        Args:
            response_content: Raw LLM response content
            language: Programming language to filter by
            
        Returns:
            List of code block contents
        """
        code_blocks = []
        
        # Pattern to match code blocks
        pattern = f'```{language}\n(.*?)\n```'
        matches = re.finditer(pattern, response_content, re.DOTALL)
        
        for match in matches:
            code_blocks.append(match.group(1).strip())
        
        return code_blocks
    
    def extract_diff_blocks(self, response_content: str) -> List[str]:
        """Extract diff blocks from response.
        
        Args:
            response_content: Raw LLM response content
            
        Returns:
            List of diff block contents
        """
        diff_blocks = []
        
        # Pattern to match diff blocks
        pattern = r'```diff\n(.*?)\n```'
        matches = re.finditer(pattern, response_content, re.DOTALL)
        
        for match in matches:
            diff_blocks.append(match.group(1).strip())
        
        return diff_blocks
    
    def validate_diff_format(self, diff_content: str) -> bool:
        """Validate that diff content is in proper unified diff format.
        
        Args:
            diff_content: Diff content to validate
            
        Returns:
            True if valid unified diff format, False otherwise
        """
        required_patterns = [
            r'^diff --git',  # Diff header
            r'^\-\-\- a/',   # Source file marker
            r'^\+\+\+ b/',   # Target file marker
            r'^@@.*@@',      # Hunk header
        ]
        
        for pattern in required_patterns:
            if not re.search(pattern, diff_content, re.MULTILINE):
                logger.warning(f"Diff validation failed: missing pattern {pattern}")
                return False
        
        return True
    
    def extract_file_path_from_diff(self, diff_content: str) -> Optional[str]:
        """Extract file path from diff content.
        
        Args:
            diff_content: Unified diff content
            
        Returns:
            File path if found, None otherwise
        """
        # Try to extract from diff header
        match = re.search(r'diff --git a/(.+?) b/', diff_content)
        if match:
            return match.group(1)
        
        # Try to extract from file markers
        match = re.search(r'^\-\-\- a/(.+?)$', diff_content, re.MULTILINE)
        if match:
            return match.group(1)
        
        return None
    
    def clean_response_content(self, response_content: str) -> str:
        """Clean and normalize response content.
        
        Args:
            response_content: Raw response content
            
        Returns:
            Cleaned response content
        """
        # Remove excessive whitespace
        cleaned = re.sub(r'\n{3,}', '\n\n', response_content)
        
        # Normalize line endings
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
        
        # Strip leading/trailing whitespace
        cleaned = cleaned.strip()
        
        return cleaned
