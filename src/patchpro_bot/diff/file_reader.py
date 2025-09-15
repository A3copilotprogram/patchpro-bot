"""File reader for loading source code content."""

import logging
from pathlib import Path
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


class FileReader:
    """Reads source code files for diff generation."""
    
    def __init__(self, base_directory: Optional[Path] = None):
        """Initialize the file reader.
        
        Args:
            base_directory: Base directory for resolving relative paths
        """
        self.base_directory = base_directory or Path.cwd()
        
    def read_file(self, file_path: str) -> Optional[str]:
        """Read content of a single file.
        
        Args:
            file_path: Path to the file (relative or absolute)
            
        Returns:
            File content as string, or None if file cannot be read
        """
        try:
            # Resolve the path
            path = self._resolve_path(file_path)
            
            if not path.exists():
                logger.warning(f"File does not exist: {path}")
                return None
            
            if not path.is_file():
                logger.warning(f"Path is not a file: {path}")
                return None
            
            # Read file content
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.debug(f"Read {len(content)} characters from {file_path}")
            return content
            
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error reading {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None
    
    def read_files(self, file_paths: List[str]) -> Dict[str, str]:
        """Read content of multiple files.
        
        Args:
            file_paths: List of file paths to read
            
        Returns:
            Dictionary mapping file paths to their content
        """
        contents = {}
        
        for file_path in file_paths:
            content = self.read_file(file_path)
            if content is not None:
                contents[file_path] = content
            
        logger.info(f"Successfully read {len(contents)}/{len(file_paths)} files")
        return contents
    
    def read_files_from_findings(self, findings) -> Dict[str, str]:
        """Read files referenced in analysis findings.
        
        Args:
            findings: List of AnalysisFinding objects
            
        Returns:
            Dictionary mapping file paths to their content
        """
        # Extract unique file paths from findings
        file_paths = list(set(finding.location.file for finding in findings))
        return self.read_files(file_paths)
    
    def _resolve_path(self, file_path: str) -> Path:
        """Resolve file path relative to base directory.
        
        Args:
            file_path: File path to resolve
            
        Returns:
            Resolved Path object
        """
        path = Path(file_path)
        
        if path.is_absolute():
            return path
        else:
            return self.base_directory / path
    
    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            path = self._resolve_path(file_path)
            return path.exists() and path.is_file()
        except Exception:
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, any]]:
        """Get information about a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file information, or None if file doesn't exist
        """
        try:
            path = self._resolve_path(file_path)
            
            if not path.exists():
                return None
            
            stat = path.stat()
            
            return {
                "path": str(path),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "suffix": path.suffix,
                "name": path.name,
            }
            
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return None
