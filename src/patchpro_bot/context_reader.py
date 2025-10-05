"""Context reader for providing file context around findings to LLM."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FindingContextReader:
    """Reads file context around findings for LLM prompts."""
    
    def __init__(self, context_lines: int = 5):
        """Initialize context reader.
        
        Args:
            context_lines: Number of lines before/after to include
        """
        self.context_lines = context_lines
    
    def get_code_context(
        self,
        file_path: str,
        line_number: int,
        end_line: Optional[int] = None
    ) -> str:
        """Read actual file content around a finding.
        
        Args:
            file_path: Path to the file
            line_number: Line number of the finding (1-indexed)
            end_line: Optional end line for multi-line findings
            
        Returns:
            Formatted code context with line numbers
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"File not found: {file_path}")
                return ""
            
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Calculate context window
            end = end_line or line_number
            start_line = max(1, line_number - self.context_lines)
            end_line_num = min(len(lines), end + self.context_lines)
            
            # Format with line numbers
            context_lines = []
            for i in range(start_line - 1, end_line_num):
                line_num = i + 1
                line_content = lines[i].rstrip('\n')
                # Mark the actual finding lines
                marker = "→" if line_number <= line_num <= end else " "
                context_lines.append(f"{marker} {line_num:4d}: {line_content}")
            
            return '\n'.join(context_lines)
            
        except Exception as e:
            logger.error(f"Error reading context from {file_path}: {e}")
            return ""
    
    def get_full_file_content(self, file_path: str) -> str:
        """Get complete file content (for small files).
        
        Args:
            file_path: Path to the file
            
        Returns:
            Full file content
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return ""
            
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""
