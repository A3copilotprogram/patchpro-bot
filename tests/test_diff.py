"""Tests for diff module."""

import pytest
from pathlib import Path

from patchpro_bot.diff import DiffGenerator, FileReader, PatchWriter
from patchpro_bot.llm.response_parser import CodeFix, DiffPatch


class TestFileReader:
    """Tests for FileReader class."""
    
    def test_init(self, temp_dir):
        """Test FileReader initialization."""
        reader = FileReader(temp_dir)
        assert reader.base_directory == temp_dir
    
    def test_init_default(self):
        """Test FileReader with default base directory."""
        reader = FileReader()
        assert reader.base_directory == Path.cwd()
    
    def test_read_file_success(self, temp_dir):
        """Test successful file reading."""
        test_file = temp_dir / "test.py"
        content = "print('hello world')"
        test_file.write_text(content)
        
        reader = FileReader(temp_dir)
        result = reader.read_file("test.py")
        
        assert result == content
    
    def test_read_file_not_found(self, temp_dir):
        """Test reading non-existent file."""
        reader = FileReader(temp_dir)
        result = reader.read_file("nonexistent.py")
        
        assert result is None
    
    def test_read_files_multiple(self, temp_dir):
        """Test reading multiple files."""
        # Create test files
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        
        content1 = "# File 1"
        content2 = "# File 2"
        
        file1.write_text(content1)
        file2.write_text(content2)
        
        reader = FileReader(temp_dir)
        results = reader.read_files(["file1.py", "file2.py", "nonexistent.py"])
        
        assert len(results) == 2
        assert results["file1.py"] == content1
        assert results["file2.py"] == content2
        assert "nonexistent.py" not in results
    
    def test_file_exists(self, temp_dir):
        """Test file existence check."""
        test_file = temp_dir / "test.py"
        test_file.write_text("content")
        
        reader = FileReader(temp_dir)
        
        assert reader.file_exists("test.py") is True
        assert reader.file_exists("nonexistent.py") is False
    
    def test_get_file_info(self, temp_dir):
        """Test getting file information."""
        test_file = temp_dir / "test.py"
        content = "test content"
        test_file.write_text(content)
        
        reader = FileReader(temp_dir)
        info = reader.get_file_info("test.py")
        
        assert info is not None
        assert info["name"] == "test.py"
        assert info["suffix"] == ".py"
        assert info["size"] == len(content)
        assert info["is_file"] is True
        assert info["is_dir"] is False
    
    def test_resolve_path_absolute(self, temp_dir):
        """Test resolving absolute paths."""
        reader = FileReader(temp_dir)
        abs_path = temp_dir / "test.py"
        
        resolved = reader._resolve_path(str(abs_path))
        assert resolved == abs_path
    
    def test_resolve_path_relative(self, temp_dir):
        """Test resolving relative paths."""
        reader = FileReader(temp_dir)
        
        resolved = reader._resolve_path("test.py")
        assert resolved == temp_dir / "test.py"


class TestDiffGenerator:
    """Tests for DiffGenerator class."""
    
    def test_init(self):
        """Test DiffGenerator initialization."""
        generator = DiffGenerator()
        assert generator.file_reader is not None
    
    def test_generate_diff_from_content(self):
        """Test generating diff from content strings."""
        original = "import os\nimport sys\n\ndef main():\n    print('hello')"
        modified = "import sys\n\ndef main():\n    print('hello')"
        
        generator = DiffGenerator()
        diff = generator.generate_diff_from_content(original, modified, "test.py")
        
        assert "diff --git a/test.py b/test.py" in diff
        assert "-import os" in diff
        assert "+++ b/test.py" in diff
        assert "--- a/test.py" in diff
    
    def test_generate_diff_no_changes(self):
        """Test generating diff with no changes."""
        content = "import sys\n\ndef main():\n    print('hello')"
        
        generator = DiffGenerator()
        diff = generator.generate_diff_from_content(content, content, "test.py")
        
        assert diff == ""
    
    def test_apply_fix_to_content_exact_match(self):
        """Test applying fix with exact content match."""
        content = "import os\nimport sys\n\ndef main():\n    pass"
        original_code = "import os"
        fixed_code = ""
        
        generator = DiffGenerator()
        result = generator._apply_fix_to_content(content, original_code, fixed_code)
        
        assert result is not None
        assert "import os" not in result
        assert "import sys" in result
    
    def test_apply_fix_to_content_no_match(self):
        """Test applying fix with no content match."""
        content = "import sys\n\ndef main():\n    pass"
        original_code = "import os"  # Not in content
        fixed_code = ""
        
        generator = DiffGenerator()
        result = generator._apply_fix_to_content(content, original_code, fixed_code)
        
        assert result is None
    
    def test_clean_code_snippet(self):
        """Test cleaning code snippets."""
        generator = DiffGenerator()
        
        # Test with indentation
        code = "    import os\n    import sys"
        cleaned = generator._clean_code_snippet(code)
        assert cleaned == "import os\nimport sys"
        
        # Test with mixed indentation
        code = "import os\n    import sys\n        print('hello')"
        cleaned = generator._clean_code_snippet(code)
        assert "import os" in cleaned
        assert "import sys" in cleaned
    
    def test_validate_diff(self):
        """Test diff validation."""
        generator = DiffGenerator()
        
        # Valid diff
        valid_diff = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,2 @@
-import os
 import sys
 def main():"""
        
        assert generator.validate_diff(valid_diff) is True
        
        # Invalid diff (missing headers)
        invalid_diff = "- some line\n+ other line"
        assert generator.validate_diff(invalid_diff) is False
        
        # Empty diff
        assert generator.validate_diff("") is False


class TestPatchWriter:
    """Tests for PatchWriter class."""
    
    def test_init(self, temp_dir):
        """Test PatchWriter initialization."""
        writer = PatchWriter(temp_dir)
        assert writer.output_directory == temp_dir
        assert temp_dir.exists()
    
    def test_write_patch(self, temp_dir):
        """Test writing a single patch."""
        diff_content = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,2 @@
-import os
 import sys"""
        
        writer = PatchWriter(temp_dir)
        patch_path = writer.write_patch(diff_content, "test.py", "test_patch.diff")
        
        assert patch_path.exists()
        assert patch_path.name == "test_patch.diff"
        
        written_content = patch_path.read_text()
        assert written_content == diff_content
    
    def test_write_patch_auto_name(self, temp_dir):
        """Test writing patch with auto-generated name."""
        diff_content = "diff content"
        
        writer = PatchWriter(temp_dir)
        patch_path = writer.write_patch(diff_content, "src/test.py")
        
        assert patch_path.exists()
        assert patch_path.name.startswith("patch_test_")
        assert patch_path.name.endswith(".diff")
    
    def test_write_multiple_patches(self, temp_dir):
        """Test writing multiple patches."""
        diffs = {
            "file1.py": "diff content 1",
            "file2.py": "diff content 2",
            "file3.py": ""  # Empty diff should be skipped
        }
        
        writer = PatchWriter(temp_dir)
        patch_paths = writer.write_multiple_patches(diffs, "test_patch")
        
        assert len(patch_paths) == 2  # Empty diff skipped
        
        for patch_path in patch_paths:
            assert patch_path.exists()
            assert patch_path.name.startswith("test_patch_")
            assert patch_path.name.endswith(".diff")
    
    def test_write_combined_patch(self, temp_dir):
        """Test writing combined patch."""
        diffs = {
            "file1.py": "diff content 1",
            "file2.py": "diff content 2"
        }
        
        writer = PatchWriter(temp_dir)
        patch_path = writer.write_combined_patch(diffs, "combined.diff")
        
        assert patch_path.exists()
        assert patch_path.name == "combined.diff"
        
        content = patch_path.read_text()
        assert "# Combined patch" in content
        assert "file1.py" in content
        assert "file2.py" in content
        assert "diff content 1" in content
        assert "diff content 2" in content
    
    def test_write_patch_summary(self, temp_dir):
        """Test writing patch summary."""
        diffs = {
            "file1.py": "--- a/file1.py\n+++ b/file1.py\n@@ -1,2 +1,1 @@\n-line1\n line2",
            "file2.py": "--- a/file2.py\n+++ b/file2.py\n@@ -1,1 +1,2 @@\n line1\n+line2"
        }
        
        patch_paths = [temp_dir / "patch1.diff", temp_dir / "patch2.diff"]
        for path in patch_paths:
            path.touch()
        
        writer = PatchWriter(temp_dir)
        summary_path = writer.write_patch_summary(diffs, patch_paths, "summary.md")
        
        assert summary_path.exists()
        assert summary_path.name == "summary.md"
        
        content = summary_path.read_text()
        assert "# Patch Summary" in content
        assert "Total patches: 2" in content
        assert "file1.py" in content
        assert "file2.py" in content
    
    def test_get_next_patch_number(self, temp_dir):
        """Test getting next patch number."""
        writer = PatchWriter(temp_dir)
        
        # No existing patches
        assert writer.get_next_patch_number() == 1
        
        # Create some existing patches
        (temp_dir / "patch_001_test.diff").touch()
        (temp_dir / "patch_003_other.diff").touch()
        
        assert writer.get_next_patch_number() == 4
    
    def test_clean_old_patches(self, temp_dir):
        """Test cleaning old patch files."""
        # Create some patch files with different timestamps
        patches = []
        for i in range(5):
            patch = temp_dir / f"patch_{i:03d}.diff"
            patch.touch()
            patches.append(patch)
        
        writer = PatchWriter(temp_dir)
        deleted_count = writer.clean_old_patches(keep_count=3)
        
        assert deleted_count == 2
        
        # Check that 3 files remain
        remaining = list(temp_dir.glob("*.diff"))
        assert len(remaining) == 3
