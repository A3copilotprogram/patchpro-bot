"""
Patch validator for fixing corrupt hunk headers.

Addresses the #1 failure mode: "corrupt patch at line X" (41% of failures).
Validates and fixes malformed @@ hunk headers by recalculating line numbers
from actual file content.
"""

import re
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger(__name__)


class PatchValidator:
    """Validates and fixes corrupt patch hunk headers.
    
    The LLM often generates patches with incorrect line numbers in @@ headers.
    This class parses the hunks, finds the actual line positions in the file,
    and fixes the headers before git apply.
    """
    
    def __init__(self):
        """Initialize the patch validator."""
        self.metrics = {
            'validated': 0,
            'fixed': 0,
            'unfixable': 0,
            'already_valid': 0
        }
    
    def validate_and_fix_patch(
        self, 
        patch_content: str,
        file_path: Path
    ) -> Tuple[str, Dict[str, Any]]:
        """Validate patch and fix corrupt hunk headers.
        
        Args:
            patch_content: The diff patch to validate
            file_path: Path to the file being patched
            
        Returns:
            Tuple of (fixed_patch_content, metrics_dict)
            
        Metrics dict contains:
            - is_valid: bool - whether patch is now valid
            - was_fixed: bool - whether we had to fix it
            - errors: List[str] - any validation errors
            - fixes_applied: List[str] - descriptions of fixes
        """
        self.metrics['validated'] += 1
        
        result_metrics = {
            'is_valid': False,
            'was_fixed': False,
            'errors': [],
            'fixes_applied': []
        }
        
        # Check if file exists
        if not file_path.exists():
            result_metrics['errors'].append(f"File not found: {file_path}")
            self.metrics['unfixable'] += 1
            return patch_content, result_metrics
        
        # Read file content
        try:
            file_content = file_path.read_text()
        except Exception as e:
            result_metrics['errors'].append(f"Failed to read file: {e}")
            self.metrics['unfixable'] += 1
            return patch_content, result_metrics
        
        # Split patch into hunks
        hunks = self._split_into_hunks(patch_content)
        
        if not hunks:
            result_metrics['errors'].append("No hunks found in patch")
            self.metrics['unfixable'] += 1
            return patch_content, result_metrics
        
        # Check if there are any @@ headers at all
        has_hunks = any('@@' in hunk for hunk in hunks)
        if not has_hunks:
            result_metrics['errors'].append("No @@ hunk headers found in patch")
            self.metrics['unfixable'] += 1
            return patch_content, result_metrics
        
        # Process each hunk
        fixed_hunks = []
        any_fixed = False
        
        for hunk in hunks:
            fixed_hunk, was_fixed, error = self._fix_hunk(hunk, file_content)
            
            if error:
                result_metrics['errors'].append(error)
            
            if was_fixed:
                any_fixed = True
                result_metrics['fixes_applied'].append(f"Fixed hunk at line {self._extract_line_number(hunk)}")
                logger.info(f"Fixed hunk header in {file_path.name}")
            
            fixed_hunks.append(fixed_hunk)
        
        # Reconstruct patch
        fixed_patch = '\n'.join(fixed_hunks)
        
        # Update metrics
        if any_fixed:
            self.metrics['fixed'] += 1
            result_metrics['was_fixed'] = True
            result_metrics['is_valid'] = True
        else:
            self.metrics['already_valid'] += 1
            result_metrics['is_valid'] = True
        
        return fixed_patch, result_metrics
    
    def _split_into_hunks(self, patch_content: str) -> List[str]:
        """Split patch into individual hunks.
        
        A hunk starts with 'diff --git' or '@@' and includes all lines
        until the next hunk or end of patch.
        """
        hunks = []
        current_hunk = []
        
        for line in patch_content.split('\n'):
            if line.startswith('diff --git') and current_hunk:
                # Start of new file diff - save previous hunk
                hunks.append('\n'.join(current_hunk))
                current_hunk = [line]
            else:
                current_hunk.append(line)
        
        # Add final hunk
        if current_hunk:
            hunks.append('\n'.join(current_hunk))
        
        return hunks
    
    def _fix_hunk(
        self,
        hunk: str,
        file_content: str
    ) -> Tuple[str, bool, Optional[str]]:
        """Fix a single hunk's header if needed.
        
        Returns:
            (fixed_hunk, was_fixed, error_message)
        """
        # Find @@ header line
        header_match = re.search(
            r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@',
            hunk
        )
        
        if not header_match:
            # No @@ header, might be diff metadata - leave as is
            return hunk, False, None
        
        # Extract header info
        old_start = int(header_match.group(1))
        old_count = int(header_match.group(2)) if header_match.group(2) else 1
        new_start = int(header_match.group(3))
        new_count = int(header_match.group(4)) if header_match.group(4) else 1
        
        # Find first context line (line without +/- prefix)
        context_line = self._find_first_context_line(hunk)
        
        if not context_line:
            # No context to validate against - leave as is
            return hunk, False, None
        
        # Find where this context actually appears in the file
        actual_line_num = self._find_line_in_file(file_content, context_line)
        
        if actual_line_num is None:
            error = f"Context not found in file: {context_line[:50]}..."
            return hunk, False, error
        
        logger.debug(f"Context line: {context_line!r}")
        logger.debug(f"Old start: {old_start}, Actual line: {actual_line_num}")
        
        # Recalculate counts from hunk content
        recalc_old_count = self._count_old_lines(hunk)
        recalc_new_count = self._count_new_lines(hunk)
        
        logger.debug(f"Header counts: old={old_count}, new={new_count}")
        logger.debug(f"Recalculated counts: old={recalc_old_count}, new={recalc_new_count}")
        
        # Check if header needs fixing (either line number OR counts are wrong)
        needs_fix = (actual_line_num != old_start or 
                     old_count != recalc_old_count or 
                     new_count != recalc_new_count)
        
        if not needs_fix:
            # Already correct
            logger.debug(f"Header already correct")
            return hunk, False, None
        
        # Build new header with correct line number and counts
        old_header = header_match.group(0)
        new_header = f'@@ -{actual_line_num},{recalc_old_count} +{actual_line_num},{recalc_new_count} @@'
        
        # Replace header in hunk
        fixed_hunk = hunk.replace(old_header, new_header, 1)
        
        logger.debug(f"Fixed hunk header: {old_header} → {new_header}")
        
        return fixed_hunk, True, None
    
    def _find_first_context_line(self, hunk: str) -> Optional[str]:
        """Find first context line in hunk to use as anchor point.
        
        Returns the FIRST actual code line (not metadata) to use for finding
        where this hunk belongs in the file. This should be a context line
        (space prefix) that appears BEFORE any changes.
        """
        lines = hunk.split('\n')
        
        # Find the first real code line (context, not metadata)
        for line in lines:
            # Skip empty lines and diff metadata
            if not line or line.startswith(('diff', '---', '+++', '@@', 'index')):
                continue
            
            # Return first context line (space prefix)
            if line.startswith(' '):
                return line[1:]  # Remove leading space
            
            # If we hit a +/- before finding context, fall back to it
            # (though this shouldn't happen in well-formed hunks)
            if line.startswith('-'):
                return line[1:]  # Remove leading -
        
        return None
    
    def _find_line_in_file(self, file_content: str, search_text: str) -> Optional[int]:
        """Find line number where text appears in file.
        
        Returns 1-indexed line number, or None if not found.
        """
        search_text = search_text.strip()
        
        for i, line in enumerate(file_content.split('\n'), start=1):
            if line.strip() == search_text:
                return i
        
        # Try fuzzy match (contains instead of exact)
        for i, line in enumerate(file_content.split('\n'), start=1):
            if search_text in line or line in search_text:
                logger.debug(f"Fuzzy matched line {i}: {line[:50]}")
                return i
        
        return None
    
    def _count_old_lines(self, hunk: str) -> int:
        """Count lines in old version (lines with ' ' or '-' prefix)."""
        count = 0
        for line in hunk.split('\n'):
            # Skip metadata lines
            if line.startswith(('diff', '---', '+++', '@@', 'index')) or not line:
                continue
            # Count context and deletion lines
            if line.startswith((' ', '-')):
                count += 1
        return count if count > 0 else 1  # At least 1
    
    def _count_new_lines(self, hunk: str) -> int:
        """Count lines in new version (lines with ' ' or '+' prefix)."""
        count = 0
        for line in hunk.split('\n'):
            # Skip metadata lines
            if line.startswith(('diff', '---', '+++', '@@', 'index')) or not line:
                continue
            # Count context and addition lines
            if line.startswith((' ', '+')):
                count += 1
        return count if count > 0 else 1  # At least 1
    
    def _extract_line_number(self, hunk: str) -> int:
        """Extract old line number from hunk header for logging."""
        header_match = re.search(r'@@ -(\\d+)', hunk)
        return int(header_match.group(1)) if header_match else 0
    
    def get_metrics(self) -> Dict[str, int]:
        """Get cumulative validation metrics."""
        return self.metrics.copy()
