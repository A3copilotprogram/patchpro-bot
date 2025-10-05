"""Validators for diff patches and other components."""

import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class DiffValidator:
    """Validates unified diff patches."""
    
    def validate_format(self, diff_content: str) -> Tuple[bool, List[str]]:
        """Check if diff has proper unified diff format.
        
        Args:
            diff_content: The diff string to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if not diff_content or not diff_content.strip():
            errors.append("Empty diff content")
            return False, errors
        
        lines = diff_content.strip().split('\n')
        
        # Must have file headers
        has_from_file = any(line.startswith('---') for line in lines)
        has_to_file = any(line.startswith('+++') for line in lines)
        
        if not has_from_file:
            errors.append("Missing '--- a/...' file header")
        if not has_to_file:
            errors.append("Missing '+++ b/...' file header")
        
        # Must have hunk headers
        has_hunk = any(line.startswith('@@') for line in lines)
        if not has_hunk:
            errors.append("Missing '@@ ... @@' hunk header")
        
        # Must have actual changes
        has_additions = any(line.startswith('+') and not line.startswith('+++') for line in lines)
        has_deletions = any(line.startswith('-') and not line.startswith('---') for line in lines)
        
        if not (has_additions or has_deletions):
            errors.append("No actual changes found (no +/- lines)")
        
        return len(errors) == 0, errors
    
    def can_apply(self, diff_content: str, repo_path: str) -> Tuple[bool, str]:
        """Check if git can apply this diff using git apply --check.
        
        Args:
            diff_content: The diff to validate
            repo_path: Path to git repository
            
        Returns:
            Tuple of (can_apply, error_message)
        """
        try:
            # Create temporary file for diff
            with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as f:
                f.write(diff_content)
                diff_file = f.name
            
            try:
                # Run git apply --check
                result = subprocess.run(
                    ['git', 'apply', '--check', '--verbose', diff_file],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    return True, ""
                else:
                    error_msg = result.stderr or result.stdout
                    return False, error_msg
                    
            finally:
                # Clean up temp file
                Path(diff_file).unlink(missing_ok=True)
                
        except subprocess.TimeoutExpired:
            return False, "git apply command timed out"
        except Exception as e:
            return False, f"Error running git apply: {e}"
    
    def extract_file_path(self, diff_content: str) -> Optional[str]:
        """Extract the target file path from diff headers.
        
        Args:
            diff_content: The diff string
            
        Returns:
            File path or None if not found
        """
        for line in diff_content.split('\n'):
            if line.startswith('+++'):
                # Format: +++ b/path/to/file
                match = re.search(r'\+\+\+ b/(.+)', line)
                if match:
                    return match.group(1)
        return None
    
    def normalize_diff_paths(self, diff_content: str, repo_path: str) -> str:
        """Normalize absolute paths to relative paths in diff.
        
        LLM often generates diffs with absolute paths like:
            --- a/opt/andela/genai/repo/src/file.py
            +++ b/opt/andela/genai/repo/src/file.py
        
        This converts them to relative paths:
            --- a/src/file.py
            +++ b/src/file.py
        
        Args:
            diff_content: The diff string with potentially absolute paths
            repo_path: Repository root path
            
        Returns:
            Normalized diff content with relative paths
        """
        if not diff_content:
            return diff_content
        
        repo_path_obj = Path(repo_path).resolve()
        repo_path_str = str(repo_path_obj)
        
        lines = []
        for line in diff_content.split('\n'):
            # Normalize --- and +++ headers
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                prefix = line[:6]  # '--- a/' or '+++ b/'
                file_path = line[6:]
                
                # Remove leading slash if present
                if file_path.startswith('/'):
                    file_path = file_path[1:]
                
                # If path contains repo path, extract relative part
                if repo_path_str in file_path:
                    # Find where repo path ends
                    repo_end = file_path.find(repo_path_str) + len(repo_path_str)
                    relative_path = file_path[repo_end:]
                    # Remove leading slash
                    relative_path = relative_path.lstrip('/')
                    file_path = relative_path
                
                line = prefix + file_path
            
            # Normalize diff --git headers
            elif line.startswith('diff --git'):
                # Format: diff --git a/path b/path
                match = re.match(r'diff --git a/(.+) b/(.+)', line)
                if match:
                    path_a = match.group(1)
                    path_b = match.group(2)
                    
                    # Normalize both paths
                    if path_a.startswith('/'):
                        path_a = path_a[1:]
                    if path_b.startswith('/'):
                        path_b = path_b[1:]
                    
                    if repo_path_str in path_a:
                        repo_end = path_a.find(repo_path_str) + len(repo_path_str)
                        path_a = path_a[repo_end:].lstrip('/')
                    
                    if repo_path_str in path_b:
                        repo_end = path_b.find(repo_path_str) + len(repo_path_str)
                        path_b = path_b[repo_end:].lstrip('/')
                    
                    line = f'diff --git a/{path_a} b/{path_b}'
            
            lines.append(line)
        
        return '\n'.join(lines)
