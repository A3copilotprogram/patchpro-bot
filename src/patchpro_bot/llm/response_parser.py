"""Parser for LLM responses."""

import json
import logging
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class ResponseType(Enum):
    """Types of responses the LLM can return."""
    CODE_FIXES = "code_fixes"
    DIFF_PATCHES = "diff_patches"


@dataclass
class ParsedResponse:
    """Container for parsed LLM response."""
    response_type: ResponseType
    code_fixes: List["CodeFix"] = None
    diff_patches: List["DiffPatch"] = None
    
    def __post_init__(self):
        """Initialize empty lists if None."""
        if self.code_fixes is None:
            self.code_fixes = []
        if self.diff_patches is None:
            self.diff_patches = []


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
    
    def parse_response(self, response_content: str, expected_type: ResponseType) -> ParsedResponse:
        """Parse LLM response based on expected type.
        
        Args:
            response_content: Raw LLM response content (JSON format)
            expected_type: The type of response we expect (CODE_FIXES or DIFF_PATCHES)
            
        Returns:
            ParsedResponse object containing the appropriate parsed data
        """
        if expected_type == ResponseType.CODE_FIXES:
            code_fixes = self.parse_code_fixes(response_content)
            return ParsedResponse(
                response_type=ResponseType.CODE_FIXES,
                code_fixes=code_fixes,
                diff_patches=[]
            )
        elif expected_type == ResponseType.DIFF_PATCHES:
            diff_patches = self.parse_diff_patches(response_content)
            return ParsedResponse(
                response_type=ResponseType.DIFF_PATCHES,
                code_fixes=[],
                diff_patches=diff_patches
            )
        else:
            logger.error(f"Unknown response type: {expected_type}")
            return ParsedResponse(
                response_type=expected_type,
                code_fixes=[],
                diff_patches=[]
            )
    
    def parse_code_fixes(self, response_content: str) -> List[CodeFix]:
        """Parse code fixes from LLM JSON response.
        
        Args:
            response_content: Raw LLM response content (JSON format)
            
        Returns:
            List of parsed code fixes
        """
        fixes = []
        
        if not response_content or not response_content.strip():
            logger.warning("Empty response content provided")
            return fixes
        
        try:
            # Parse JSON response
            response_data = json.loads(response_content.strip())
            
            # Extract fixes from the JSON structure
            fixes_data = response_data.get("fixes", [])
            
            for fix_data in fixes_data:
                try:
                    fix = CodeFix(
                        fix_number=fix_data.get("fix_number", 0),
                        description=fix_data.get("description", ""),
                        file_path=fix_data.get("file_path", ""),
                        lines=fix_data.get("lines", ""),
                        issue=fix_data.get("issue", "No issue specified"),
                        original_code=fix_data.get("original_code", ""),
                        fixed_code=fix_data.get("fixed_code", ""),
                        rationale=fix_data.get("rationale", "No rationale provided"),
                    )
                    fixes.append(fix)
                    logger.debug(f"Parsed fix #{fix.fix_number} for {fix.file_path}")
                except Exception as e:
                    logger.error(f"Failed to parse fix from JSON data: {e}")
                    continue
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            # Fallback: try to extract JSON from response if it's wrapped in other text
            cleaned_content = self._extract_json_from_response(response_content)
            if cleaned_content:
                try:
                    response_data = json.loads(cleaned_content)
                    fixes_data = response_data.get("fixes", [])
                    
                    for fix_data in fixes_data:
                        try:
                            fix = CodeFix(
                                fix_number=fix_data.get("fix_number", 0),
                                description=fix_data.get("description", ""),
                                file_path=fix_data.get("file_path", ""),
                                lines=fix_data.get("lines", ""),
                                issue=fix_data.get("issue", "No issue specified"),
                                original_code=fix_data.get("original_code", ""),
                                fixed_code=fix_data.get("fixed_code", ""),
                                rationale=fix_data.get("rationale", "No rationale provided"),
                            )
                            fixes.append(fix)
                            logger.debug(f"Parsed fix #{fix.fix_number} for {fix.file_path}")
                        except Exception as e:
                            logger.error(f"Failed to parse fix from fallback JSON: {e}")
                            continue
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON even after cleanup")
        except Exception as e:
            logger.error(f"Unexpected error parsing code fixes: {e}")
        
        logger.info(f"Parsed {len(fixes)} code fixes from response")
        return fixes
    
    def parse_diff_patches(self, response_content: str) -> List[DiffPatch]:
        """Parse unified diff patches from LLM JSON response.
        
        Args:
            response_content: Raw LLM response content (JSON format)
            
        Returns:
            List of parsed diff patches
        """
        patches = []
        
        if not response_content or not response_content.strip():
            logger.warning("Empty response content provided")
            return patches
        
        try:
            # Parse JSON response
            response_data = json.loads(response_content.strip())
            
            # Handle both single patch and multiple patches formats
            if "patch" in response_data:
                # Single patch format
                patch_data = response_data["patch"]
                patch = DiffPatch(
                    file_path=patch_data.get("file_path", ""),
                    diff_content=patch_data.get("diff_content", ""),
                    summary=patch_data.get("summary", None),
                )
                patches.append(patch)
                logger.debug(f"Parsed single diff patch for {patch.file_path}")
                
            elif "patches" in response_data:
                # Multiple patches format
                patches_data = response_data["patches"]
                for patch_data in patches_data:
                    try:
                        patch = DiffPatch(
                            file_path=patch_data.get("file_path", ""),
                            diff_content=patch_data.get("diff_content", ""),
                            summary=patch_data.get("summary", None),
                        )
                        patches.append(patch)
                        logger.debug(f"Parsed diff patch for {patch.file_path}")
                    except Exception as e:
                        logger.error(f"Failed to parse patch from JSON data: {e}")
                        continue
                        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            # Fallback: try to extract JSON from response if it's wrapped in other text
            cleaned_content = self._extract_json_from_response(response_content)
            if cleaned_content:
                try:
                    response_data = json.loads(cleaned_content)
                    
                    if "patch" in response_data:
                        patch_data = response_data["patch"]
                        patch = DiffPatch(
                            file_path=patch_data.get("file_path", ""),
                            diff_content=patch_data.get("diff_content", ""),
                            summary=patch_data.get("summary", None),
                        )
                        patches.append(patch)
                        logger.debug(f"Parsed single diff patch for {patch.file_path}")
                        
                    elif "patches" in response_data:
                        patches_data = response_data["patches"]
                        for patch_data in patches_data:
                            try:
                                patch = DiffPatch(
                                    file_path=patch_data.get("file_path", ""),
                                    diff_content=patch_data.get("diff_content", ""),
                                    summary=patch_data.get("summary", None),
                                )
                                patches.append(patch)
                                logger.debug(f"Parsed diff patch for {patch.file_path}")
                            except Exception as e:
                                logger.error(f"Failed to parse patch from fallback JSON: {e}")
                                continue
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON even after cleanup")
        except Exception as e:
            logger.error(f"Unexpected error parsing diff patches: {e}")
        
        logger.info(f"Parsed {len(patches)} diff patches from response")
        return patches
    
    def _extract_json_from_response(self, response_content: str) -> Optional[str]:
        """Extract JSON from response content that may contain additional text.
        
        Args:
            response_content: Raw response content
            
        Returns:
            Extracted JSON string or None if not found
        """
        # Try to find JSON block between ```json markers
        json_start_markers = ["```json\n", "```json ", "```\n{", "```{"]
        json_end_markers = ["```", "\n```"]
        
        for start_marker in json_start_markers:
            start_idx = response_content.find(start_marker)
            if start_idx != -1:
                json_start = start_idx + len(start_marker)
                for end_marker in json_end_markers:
                    end_idx = response_content.find(end_marker, json_start)
                    if end_idx != -1:
                        return response_content[json_start:end_idx].strip()
        
        # Try to find JSON by looking for opening and closing braces
        open_brace = response_content.find('{')
        if open_brace != -1:
            brace_count = 0
            for i, char in enumerate(response_content[open_brace:], open_brace):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return response_content[open_brace:i+1]
        
        return None
    
    def extract_code_blocks(self, response_content: str, language: str = "python") -> List[str]:
        """Extract code blocks from response.
        
        Note: This method is deprecated in favor of JSON-based parsing.
        
        Args:
            response_content: Raw LLM response content
            language: Programming language to filter by
            
        Returns:
            List of code block contents
        """
        logger.warning("extract_code_blocks is deprecated - use JSON-based parsing instead")
        return []
    
    def extract_diff_blocks(self, response_content: str) -> List[str]:
        """Extract diff blocks from response.
        
        Note: This method is deprecated in favor of JSON-based parsing.
        
        Args:
            response_content: Raw LLM response content
            
        Returns:
            List of diff block contents
        """
        logger.warning("extract_diff_blocks is deprecated - use JSON-based parsing instead")
        return []
    
    def validate_diff_format(self, diff_content: str) -> bool:
        """Validate that diff content is in proper unified diff format.
        
        Args:
            diff_content: Diff content to validate
            
        Returns:
            True if valid unified diff format, False otherwise
        """
        required_patterns = [
            'diff --git',  # Diff header
            '--- a/',      # Source file marker
            '+++ b/',      # Target file marker
            '@@',          # Hunk header
        ]
        
        for pattern in required_patterns:
            if pattern not in diff_content:
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
        # Look for diff header
        lines = diff_content.split('\n')
        for line in lines:
            if line.startswith('diff --git a/'):
                # Extract path between 'a/' and ' b/'
                try:
                    start_idx = line.find('a/') + 2
                    end_idx = line.find(' b/')
                    if start_idx > 1 and end_idx > start_idx:
                        return line[start_idx:end_idx]
                except Exception:
                    continue
                    
            elif line.startswith('--- a/'):
                # Extract path after 'a/'
                try:
                    return line[6:]  # Remove '--- a/' prefix
                except Exception:
                    continue
        
        return None
    
    def clean_response_content(self, response_content: str) -> str:
        """Clean and normalize response content.
        
        Args:
            response_content: Raw response content
            
        Returns:
            Cleaned response content
        """
        # Simple cleaning without regex
        # Remove excessive whitespace by splitting and rejoining
        lines = response_content.split('\n')
        cleaned_lines = []
        empty_line_count = 0
        
        for line in lines:
            if line.strip() == '':
                empty_line_count += 1
                if empty_line_count <= 2:  # Allow max 2 consecutive empty lines
                    cleaned_lines.append('')
            else:
                empty_line_count = 0
                cleaned_lines.append(line)
        
        # Normalize line endings and strip
        cleaned = '\n'.join(cleaned_lines)
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
        cleaned = cleaned.strip()
        
        return cleaned
