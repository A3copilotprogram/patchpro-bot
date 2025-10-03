"""Unified diff generator."""

import logging
import difflib
import hashlib
from datetime import datetime
from typing import List, Dict, Optional

from ..llm.response_parser import DiffPatch, CodeFix
from .file_reader import FileReader


logger = logging.getLogger(__name__)


class DiffGenerator:
    """Generates unified diff patches from code fixes."""
    
    def __init__(self, file_reader: Optional[FileReader] = None):
        """Initialize the diff generator.
        
        Args:
            file_reader: FileReader instance for loading source files
        """
        self.file_reader = file_reader or FileReader()
    
    def generate_diff_from_fix(
        self,
        code_fix: CodeFix,
        original_content: Optional[str] = None,
    ) -> Optional[str]:
        """Generate unified diff from a CodeFix object.
        
        Args:
            code_fix: CodeFix containing original and fixed code
            original_content: Original file content (if not provided, will be read)
            
        Returns:
            Unified diff string, or None if generation fails
        """
        try:
            # Get original content if not provided
            if original_content is None:
                original_content = self.file_reader.read_file(code_fix.file_path)
                if original_content is None:
                    logger.error(f"Cannot read original file: {code_fix.file_path}")
                    return None
            
            # Apply the fix to get modified content
            modified_content = self._apply_fix_to_content(
                original_content,
                code_fix.original_code,
                code_fix.fixed_code,
            )
            
            if modified_content is None:
                logger.error(f"Failed to apply fix to {code_fix.file_path}")
                return None
            
            # Generate unified diff
            diff = self._generate_unified_diff(
                original_content,
                modified_content,
                code_fix.file_path,
            )
            
            # Normalize whitespace in the diff
            diff = self.normalize_diff_whitespace(diff)
            
            logger.info(f"Generated diff for {code_fix.file_path}")
            return diff
            
        except Exception as e:
            logger.error(f"Error generating diff for {code_fix.file_path}: {e}")
            return None
    
    def generate_diff_from_content(
        self,
        original_content: str,
        modified_content: str,
        file_path: str,
    ) -> str:
        """Generate unified diff from original and modified content.
        
        Args:
            original_content: Original file content
            modified_content: Modified file content
            file_path: Path to the file
            
        Returns:
            Unified diff string
        """
        diff = self._generate_unified_diff(
            original_content,
            modified_content,
            file_path,
        )
        return self.normalize_diff_whitespace(diff)
    
    def generate_diff_from_patch(self, diff_patch: DiffPatch) -> str:
        """Extract and validate diff from DiffPatch object.
        
        Args:
            diff_patch: DiffPatch containing diff content
            
        Returns:
            Unified diff string
        """
        # The diff content should already be in unified diff format
        diff_content = diff_patch.diff_content
        
        # Validate and potentially clean up the diff
        if not diff_content.startswith('diff --git'):
            # Add proper diff header if missing
            file_path = diff_patch.file_path
            diff_content = f"""diff --git a/{file_path} b/{file_path}
index 0000000..1111111 100644
--- a/{file_path}
+++ b/{file_path}
{diff_content}"""
        
        return diff_content
    
    def generate_multiple_diffs(
        self,
        code_fixes: List[CodeFix],
    ) -> Dict[str, str]:
        """Generate diffs for multiple code fixes.
        
        Args:
            code_fixes: List of CodeFix objects
            
        Returns:
            Dictionary mapping file paths to their diffs
        """
        diffs = {}
        
        # Group fixes by file
        fixes_by_file = {}
        for fix in code_fixes:
            if fix.file_path not in fixes_by_file:
                fixes_by_file[fix.file_path] = []
            fixes_by_file[fix.file_path].append(fix)
        
        # Generate diff for each file
        for file_path, file_fixes in fixes_by_file.items():
            try:
                # Read original content once per file
                original_content = self.file_reader.read_file(file_path)
                if original_content is None:
                    logger.error(f"Cannot read file: {file_path}")
                    continue
                
                # Apply all fixes to the file
                modified_content = original_content
                
                for fix in file_fixes:
                    modified_content = self._apply_fix_to_content(
                        modified_content,
                        fix.original_code,
                        fix.fixed_code,
                    )
                    
                    if modified_content is None:
                        logger.error(f"Failed to apply fix in {file_path}")
                        break
                
                if modified_content is not None:
                    # Generate unified diff
                    diff = self._generate_unified_diff(
                        original_content,
                        modified_content,
                        file_path,
                    )
                    # Normalize whitespace in the diff
                    diff = self.normalize_diff_whitespace(diff)
                    diffs[file_path] = diff
                    logger.info(f"Generated diff for {file_path} with {len(file_fixes)} fixes")
                
            except Exception as e:
                logger.error(f"Error generating diff for {file_path}: {e}")
                continue
        
        return diffs
    
    def _apply_fix_to_content(
        self,
        content: str,
        original_code: str,
        fixed_code: str,
    ) -> Optional[str]:
        """Apply a code fix to file content.
        
        Args:
            content: Original file content
            original_code: Original code to replace
            fixed_code: Fixed code to replace with
            
        Returns:
            Modified content, or None if replacement fails
        """
        try:
            # Clean up code snippets (remove common indentation patterns)
            original_clean = self._clean_code_snippet(original_code)
            fixed_clean = self._clean_code_snippet(fixed_code)
            
            # Always use line-by-line replacement to ensure proper indentation
            # Skip the exact replacement to avoid indentation issues
            content_lines = content.splitlines()
            original_lines = original_clean.splitlines()
            fixed_lines = fixed_clean.splitlines()
            
            # Find the sequence of original lines in content
            for i in range(len(content_lines) - len(original_lines) + 1):
                match = True
                base_indent = None
                
                for j, orig_line in enumerate(original_lines):
                    content_line = content_lines[i + j]
                    content_line_stripped = content_line.strip()
                    orig_line_stripped = orig_line.strip()
                    
                    # Skip empty lines comparison
                    if not content_line_stripped and not orig_line_stripped:
                        continue
                    
                    if content_line_stripped != orig_line_stripped:
                        match = False
                        break
                    
                    # For the first non-empty line, capture the base indentation
                    if base_indent is None and content_line_stripped:
                        base_indent = len(content_line) - len(content_line.lstrip())
                
                if match:
                    # Analyze the fixed code for proper indentation
                    logger.debug(f"Found match at position {i}, base_indent={base_indent}")
                    adjusted_fixed_lines = self._apply_proper_indentation(
                        fixed_lines, base_indent, content_lines, i
                    )
                    logger.debug(f"Adjusted fixed lines: {adjusted_fixed_lines}")
                    
                    # Special handling for context manager replacements
                    if self._is_context_manager_replacement(original_lines, fixed_lines):
                        logger.debug("Detected context manager replacement")
                        # Need to handle surrounding lines that should be modified
                        adjusted_fixed_lines, new_end_index = self._handle_context_manager_replacement(
                            content_lines, i, len(original_lines), adjusted_fixed_lines
                        )
                        logger.debug(f"After context manager handling: {adjusted_fixed_lines}, end_index={new_end_index}")
                        replacement_end = new_end_index
                    else:
                        replacement_end = i + len(original_lines)
                    
                    # Replace the matched lines
                    new_lines = (
                        content_lines[:i] +
                        adjusted_fixed_lines +
                        content_lines[replacement_end:]
                    )
                    return '\n'.join(new_lines)
            
            # Try fuzzy matching as a fallback
            result = self._try_fuzzy_matching(content, original_clean, fixed_clean)
            if result:
                return result
            
            logger.warning(f"Could not find exact match for code replacement. Original: {repr(original_clean[:50])}...")
            return None
            
        except Exception as e:
            logger.error(f"Error applying fix: {e}")
            return None
    
    def _clean_code_snippet(self, code: str) -> str:
        """Clean up code snippet for matching.
        
        Args:
            code: Code snippet to clean
            
        Returns:
            Cleaned code snippet
        """
        # Split into lines but don't strip the entire code first
        lines = code.splitlines()
        
        # Remove completely empty lines at start and end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        # Remove common leading whitespace, but handle inconsistent indentation
        if lines:
            # Find minimum indentation (excluding empty lines)
            indentations = []
            for line in lines:
                if line.strip():  # Skip empty lines
                    indent = len(line) - len(line.lstrip())
                    indentations.append(indent)
            
            if indentations:
                min_indent = min(indentations)
                # Only remove common indentation if ALL non-empty lines have at least that much
                if min_indent > 0:
                    # Check if all non-empty lines can have this indentation removed
                    can_remove = True
                    for line in lines:
                        if line.strip() and not line.startswith(' ' * min_indent):
                            can_remove = False
                            break
                    
                    if can_remove:
                        lines = [line[min_indent:] if line.strip() else '' for line in lines]
        
        return '\n'.join(lines)
    
    def _apply_proper_indentation(
        self, 
        fixed_lines: List[str], 
        base_indent: int, 
        content_lines: List[str], 
        match_position: int
    ) -> List[str]:
        """Apply proper indentation to fixed lines based on context.
        
        Args:
            fixed_lines: Lines from the fixed code
            base_indent: Base indentation level from the original context
            content_lines: All content lines for context analysis
            match_position: Position where the match was found
            
        Returns:
            List of properly indented lines
        """
        if base_indent is None:
            base_indent = 0
        
        adjusted_fixed_lines = []
        current_indent = base_indent
        
        for line_idx, fixed_line in enumerate(fixed_lines):
            if not fixed_line.strip():
                adjusted_fixed_lines.append('')
                continue
            
            fixed_line_content = fixed_line.strip()
            
            # Check if this is a context manager line or other block statement
            if (fixed_line_content.startswith('with ') or 
                fixed_line_content.startswith('if ') or 
                fixed_line_content.startswith('for ') or 
                fixed_line_content.startswith('while ') or 
                fixed_line_content.startswith('def ') or 
                fixed_line_content.startswith('class ')) and fixed_line_content.endswith(':'):
                # Apply base indentation to the block statement
                adjusted_line = ' ' * base_indent + fixed_line_content
                adjusted_fixed_lines.append(adjusted_line)
                # Next lines should be indented more (assuming 4-space indentation)
                current_indent = base_indent + 4
            elif (fixed_line_content.startswith('except') or 
                  fixed_line_content.startswith('finally') or 
                  fixed_line_content.startswith('else') or 
                  fixed_line_content.startswith('elif')):
                # These are at the same level as the original block
                adjusted_line = ' ' * base_indent + fixed_line_content
                adjusted_fixed_lines.append(adjusted_line)
                if fixed_line_content.endswith(':'):
                    current_indent = base_indent + 4
            else:
                # Regular line - use current indentation level
                adjusted_line = ' ' * current_indent + fixed_line_content
                adjusted_fixed_lines.append(adjusted_line)
        
        return adjusted_fixed_lines
    
    def _is_context_manager_replacement(self, original_lines: List[str], fixed_lines: List[str]) -> bool:
        """Check if this is a context manager replacement.
        
        Args:
            original_lines: Original code lines
            fixed_lines: Fixed code lines
            
        Returns:
            True if this is a context manager replacement
        """
        # Check if original code has open() call and fixed code has with statement
        has_open_call = any('open(' in line for line in original_lines)
        has_with_statement = any('with ' in line and line.strip().endswith(':') for line in fixed_lines)
        
        # Also check for patterns where we're replacing file operations
        has_file_assignment = any('=' in line and 'open(' in line for line in original_lines)
        
        return (has_open_call and has_with_statement) or has_file_assignment
    
    def _handle_context_manager_replacement(
        self, 
        content_lines: List[str], 
        start_index: int, 
        original_length: int,
        adjusted_fixed_lines: List[str]
    ) -> tuple[List[str], int]:
        """Handle context manager replacement including surrounding lines.
        
        Args:
            content_lines: All content lines
            start_index: Start index of replacement
            original_length: Length of original code being replaced
            adjusted_fixed_lines: Already adjusted fixed lines
            
        Returns:
            Tuple of (final_lines, end_index)
        """
        # For context manager transformations, we need to look at the broader pattern
        # The original may be just "file = open(filename)" but we need to transform:
        # 1. file = open(filename) -> with open(filename) as file:
        # 2. content = file.read() -> content = file.read() (indented inside with block)
        # 3. file.close() -> remove this line
        
        final_lines = adjusted_fixed_lines[:]
        end_index = start_index + original_length
        base_indent = len(content_lines[start_index]) - len(content_lines[start_index].lstrip())
        
        # Look ahead to collect related lines for context manager transformation
        subsequent_lines = []
        current_index = end_index
        
        # Scan forward to find related lines (file operations)
        while current_index < len(content_lines):
            line = content_lines[current_index].strip()
            line_indent = len(content_lines[current_index]) - len(content_lines[current_index].lstrip())
            
            # Skip empty lines
            if not line:
                current_index += 1
                continue
            
            # Stop if we encounter a different indentation level (e.g., method definition)
            if line_indent < base_indent:
                break
                
            # Check if this line should be part of the context manager
            if (line_indent == base_indent and 
                ('file.' in line or 'close()' in line or line.startswith('content ='))):
                
                if 'close()' in line:
                    # Remove close() calls - don't add to final lines
                    current_index += 1
                    end_index = current_index
                    continue
                else:
                    # This line should be indented inside the context manager
                    indented_line = ' ' * (base_indent + 4) + line
                    subsequent_lines.append(indented_line)
                    current_index += 1
                    end_index = current_index
            else:
                # This line doesn't belong to the context manager
                break
        
        # Add the subsequent lines to the final result
        final_lines.extend(subsequent_lines)
        
        return final_lines, end_index
    
    def _try_fuzzy_matching(
        self, 
        content: str, 
        original_clean: str, 
        fixed_clean: str
    ) -> Optional[str]:
        """Try fuzzy matching for code replacement.
        
        Args:
            content: Original file content
            original_clean: Cleaned original code
            fixed_clean: Cleaned fixed code
            
        Returns:
            Modified content, or None if no match found
        """
        import difflib
        
        content_lines = content.splitlines()
        original_lines = original_clean.splitlines()
        
        # Only try fuzzy matching for reasonable cases
        if len(original_lines) == 0 or len(content_lines) < len(original_lines):
            return None
        
        # Try to find partial matches with high similarity threshold
        best_match_ratio = 0.9  # Increased threshold to be more conservative
        best_match_start = None
        
        for i in range(len(content_lines) - len(original_lines) + 1):
            content_snippet = '\n'.join(content_lines[i:i + len(original_lines)])
            similarity = difflib.SequenceMatcher(None, content_snippet.strip(), original_clean.strip()).ratio()
            
            if similarity >= best_match_ratio:
                best_match_ratio = similarity
                best_match_start = i
        
        if best_match_start is not None:
            # Apply the fix with the best fuzzy match
            logger.info(f"Using fuzzy match with {best_match_ratio:.2f} similarity")
            base_indent = len(content_lines[best_match_start]) - len(content_lines[best_match_start].lstrip())
            
            fixed_lines = fixed_clean.splitlines()
            adjusted_fixed_lines = self._apply_proper_indentation(
                fixed_lines, base_indent, content_lines, best_match_start
            )
            
            new_lines = (
                content_lines[:best_match_start] +
                adjusted_fixed_lines +
                content_lines[best_match_start + len(original_lines):]
            )
            return '\n'.join(new_lines)
        
        return None
    
    def _generate_unified_diff(
        self,
        original: str,
        modified: str,
        file_path: str,
    ) -> str:
        """Generate unified diff between original and modified content.
        
        Args:
            original: Original file content
            modified: Modified file content
            file_path: Path to the file
            
        Returns:
            Unified diff string
        """
        # Ensure both contents end with newline for proper diff generation
        if original and not original.endswith('\n'):
            original += '\n'
        if modified and not modified.endswith('\n'):
            modified += '\n'
        
        # Split into lines for difflib
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        # Generate timestamp
        timestamp = datetime.now().isoformat()
        
        # Generate hash placeholders (simplified)
        original_hash = hashlib.md5(original.encode()).hexdigest()[:7]
        modified_hash = hashlib.md5(modified.encode()).hexdigest()[:7]
        
        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm='',
        ))
        
        if not diff_lines:
            # No differences
            return ""
        
        # Add git-style header
        git_header = f"""diff --git a/{file_path} b/{file_path}
index {original_hash}..{modified_hash} 100644"""
        
        # Process diff lines to handle line endings correctly
        processed_lines = []
        for line in diff_lines:
            if line.endswith('\n'):
                # Content lines from difflib already have newlines
                processed_lines.append(line.rstrip('\n'))
            else:
                # Header lines don't have newlines
                processed_lines.append(line)
        
        # Combine header with diff using single newlines
        diff_content = git_header + '\n' + '\n'.join(processed_lines)
        
        return diff_content
    
    def validate_diff(self, diff_content: str) -> bool:
        """Validate that diff content is properly formatted.
        
        Args:
            diff_content: Diff content to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not diff_content.strip():
            return False
        
        lines = diff_content.splitlines()
        
        # Check for required headers
        has_git_header = any(line.startswith('diff --git') for line in lines)
        has_file_headers = any(line.startswith('---') for line in lines) and \
                          any(line.startswith('+++') for line in lines)
        has_hunk_header = any(line.startswith('@@') for line in lines)
        
        return has_git_header and has_file_headers and has_hunk_header
    
    def normalize_diff_whitespace(self, diff_content: str) -> str:
        """Normalize whitespace in diff content.
        
        Args:
            diff_content: Diff content to normalize
            
        Returns:
            Normalized diff content
        """
        if not diff_content:
            return diff_content
        
        lines = diff_content.splitlines()
        normalized_lines = []
        
        for line in lines:
            # Remove trailing whitespace from all lines
            # This ensures consistent formatting across the entire diff
            normalized_lines.append(line.rstrip())
        
        return '\n'.join(normalized_lines)
