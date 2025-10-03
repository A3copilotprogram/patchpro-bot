"""Patch writer for saving unified diff patches to files."""

import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


class PatchWriter:
    """Writes unified diff patches to files."""
    
    def __init__(self, output_directory: Path = Path("artifact")):
        """Initialize the patch writer.
        
        Args:
            output_directory: Directory to save patch files
        """
        self.output_directory = output_directory
        self.output_directory.mkdir(parents=True, exist_ok=True)
    
    def write_patch(
        self,
        diff_content: str,
        file_path: str,
        patch_name: Optional[str] = None,
    ) -> Path:
        """Write a single patch to file.
        
        Args:
            diff_content: Unified diff content
            file_path: Original file path (used for naming if patch_name not provided)
            patch_name: Optional custom patch filename
            
        Returns:
            Path to the written patch file
        """
        if not patch_name:
            # Generate patch name from file path
            file_stem = Path(file_path).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            patch_name = f"patch_{file_stem}_{timestamp}.diff"
        
        # Ensure patch name ends with .diff
        if not patch_name.endswith('.diff'):
            patch_name += '.diff'
        
        patch_path = self.output_directory / patch_name
        
        try:
            with open(patch_path, 'w', encoding='utf-8') as f:
                f.write(diff_content)
            
            logger.info(f"Wrote patch to {patch_path}")
            return patch_path
            
        except Exception as e:
            logger.error(f"Error writing patch to {patch_path}: {e}")
            raise
    
    def write_multiple_patches(
        self,
        diffs: Dict[str, str],
        prefix: str = "patch",
    ) -> List[Path]:
        """Write multiple patches to separate files.
        
        Args:
            diffs: Dictionary mapping file paths to diff content
            prefix: Prefix for patch filenames
            
        Returns:
            List of paths to written patch files
        """
        patch_paths = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for i, (file_path, diff_content) in enumerate(diffs.items(), 1):
            if not diff_content.strip():
                logger.warning(f"Skipping empty diff for {file_path}")
                continue
            
            # Generate unique patch name
            file_stem = Path(file_path).stem
            patch_name = f"{prefix}_{i:03d}_{file_stem}_{timestamp}.diff"
            
            try:
                patch_path = self.write_patch(diff_content, file_path, patch_name)
                patch_paths.append(patch_path)
            except Exception as e:
                logger.error(f"Failed to write patch for {file_path}: {e}")
                continue
        
        logger.info(f"Wrote {len(patch_paths)} patch files")
        return patch_paths
    
    def write_combined_patch(
        self,
        diffs: Dict[str, str],
        patch_name: Optional[str] = None,
    ) -> Path:
        """Write multiple diffs to a single combined patch file.
        
        Args:
            diffs: Dictionary mapping file paths to diff content
            patch_name: Optional custom patch filename
            
        Returns:
            Path to the written combined patch file
        """
        if not patch_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            patch_name = f"patch_combined_{timestamp}.diff"
        
        # Ensure patch name ends with .diff
        if not patch_name.endswith('.diff'):
            patch_name += '.diff'
        
        patch_path = self.output_directory / patch_name
        
        try:
            with open(patch_path, 'w', encoding='utf-8') as f:
                # Write header comment
                f.write(f"# Combined patch generated on {datetime.now().isoformat()}\n")
                f.write(f"# Contains fixes for {len(diffs)} files\n")
                f.write("#\n")
                
                for file_path in sorted(diffs.keys()):
                    f.write(f"# {file_path}\n")
                
                f.write("\n")
                
                # Write each diff
                for file_path, diff_content in sorted(diffs.items()):
                    if not diff_content.strip():
                        continue
                    
                    # Ensure diff content ends with single newline
                    clean_diff = diff_content.rstrip() + '\n'
                    f.write(clean_diff)
                    f.write("\n")
            
            logger.info(f"Wrote combined patch to {patch_path}")
            return patch_path
            
        except Exception as e:
            logger.error(f"Error writing combined patch to {patch_path}: {e}")
            raise
    
    def write_patch_summary(
        self,
        diffs: Dict[str, str],
        patch_paths: List[Path],
        summary_name: Optional[str] = None,
    ) -> Path:
        """Write a summary of generated patches.
        
        Args:
            diffs: Dictionary mapping file paths to diff content
            patch_paths: List of written patch file paths
            summary_name: Optional custom summary filename
            
        Returns:
            Path to the written summary file
        """
        if not summary_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_name = f"patch_summary_{timestamp}.md"
        
        summary_path = self.output_directory / summary_name
        
        try:
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write("# Patch Summary\n\n")
                f.write(f"Generated on: {datetime.now().isoformat()}\n")
                f.write(f"Total patches: {len(patch_paths)}\n")
                f.write(f"Total files modified: {len(diffs)}\n\n")
                
                f.write("## Generated Patch Files\n\n")
                for patch_path in patch_paths:
                    f.write(f"- `{patch_path.name}`\n")
                
                f.write("\n## Modified Files\n\n")
                for file_path, diff_content in sorted(diffs.items()):
                    # Count changes
                    lines = diff_content.splitlines()
                    additions = len([line for line in lines if line.startswith('+')])
                    deletions = len([line for line in lines if line.startswith('-')])
                    
                    f.write(f"### `{file_path}`\n\n")
                    f.write(f"- Lines added: {additions}\n")
                    f.write(f"- Lines removed: {deletions}\n\n")
            
            logger.info(f"Wrote patch summary to {summary_path}")
            return summary_path
            
        except Exception as e:
            logger.error(f"Error writing patch summary to {summary_path}: {e}")
            raise
    
    def get_next_patch_number(self, prefix: str = "patch") -> int:
        """Get the next available patch number.
        
        Args:
            prefix: Prefix to look for in existing files
            
        Returns:
            Next available patch number
        """
        existing_patches = list(self.output_directory.glob(f"{prefix}_*.diff"))
        
        if not existing_patches:
            return 1
        
        # Extract numbers from existing patch names
        numbers = []
        for patch in existing_patches:
            name = patch.stem
            parts = name.split('_')
            for part in parts:
                if part.isdigit():
                    numbers.append(int(part))
                    break
        
        return max(numbers, default=0) + 1
    
    def clean_old_patches(self, keep_count: int = 10) -> int:
        """Clean up old patch files, keeping only the most recent ones.
        
        Args:
            keep_count: Number of recent patches to keep
            
        Returns:
            Number of files deleted
        """
        patch_files = list(self.output_directory.glob("*.diff"))
        
        if len(patch_files) <= keep_count:
            return 0
        
        # Sort by modification time (newest first)
        patch_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Delete older files
        deleted_count = 0
        for patch_file in patch_files[keep_count:]:
            try:
                patch_file.unlink()
                deleted_count += 1
                logger.debug(f"Deleted old patch: {patch_file}")
            except Exception as e:
                logger.error(f"Error deleting {patch_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old patch files")
        
        return deleted_count
