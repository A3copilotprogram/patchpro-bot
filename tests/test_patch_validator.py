"""
Unit tests for PatchValidator.

Tests the patch validation and hunk header fixing logic.
"""

import pytest
from pathlib import Path
from patchpro_bot.patch_validator import PatchValidator


@pytest.fixture
def validator():
    """Create PatchValidator instance."""
    return PatchValidator()


@pytest.fixture
def sample_file(tmp_path):
    """Create a sample Python file for testing."""
    file_path = tmp_path / "example.py"
    file_path.write_text("""import os
import sys

def main():
    print("Hello, World!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
""")
    return file_path


def test_validator_initialization(validator):
    """Test PatchValidator initializes with empty metrics."""
    assert validator.metrics['validated'] == 0
    assert validator.metrics['fixed'] == 0
    assert validator.metrics['unfixable'] == 0
    assert validator.metrics['already_valid'] == 0


def test_valid_patch_not_modified(validator, sample_file):
    """Test that already-valid patches are not modified."""
    # Patch with correct line numbers
    patch = """diff --git a/example.py b/example.py
index abc123..def456 100644
--- a/example.py
+++ b/example.py
@@ -1,2 +1,1 @@
-import os
 import sys
"""
    
    fixed_patch, metrics = validator.validate_and_fix_patch(patch, sample_file)
    
    assert metrics['is_valid']
    assert not metrics['was_fixed']
    assert len(metrics['errors']) == 0
    assert fixed_patch == patch  # Unchanged


def test_corrupt_patch_fixed(validator, sample_file):
    """Test that corrupt patch with wrong line numbers gets fixed."""
    # Patch with WRONG line numbers (says line 10 but content is at line 1)
    corrupt_patch = """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -10,2 +10,1 @@
-import os
 import sys
"""
    
    fixed_patch, metrics = validator.validate_and_fix_patch(corrupt_patch, sample_file)
    
    assert metrics['is_valid']
    assert metrics['was_fixed']
    assert len(metrics['fixes_applied']) > 0
    assert '@@ -1,' in fixed_patch  # Fixed to correct line 1
    assert '@@ -10,' not in fixed_patch  # Old incorrect line gone


def test_file_not_found(validator, tmp_path):
    """Test handling of non-existent file."""
    patch = """diff --git a/missing.py b/missing.py
@@ -1,1 +1,1 @@
-old line
+new line
"""
    
    missing_file = tmp_path / "missing.py"
    fixed_patch, metrics = validator.validate_and_fix_patch(patch, missing_file)
    
    assert not metrics['is_valid']
    assert not metrics['was_fixed']
    assert any('not found' in err.lower() for err in metrics['errors'])


def test_no_hunks_in_patch(validator, sample_file):
    """Test handling of patch with no @@ hunks."""
    patch = """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
"""
    
    fixed_patch, metrics = validator.validate_and_fix_patch(patch, sample_file)
    
    assert not metrics['is_valid']
    assert any('no hunks' in err.lower() for err in metrics['errors'])


def test_context_not_found_in_file(validator, sample_file):
    """Test handling when patch context doesn't exist in file."""
    # Patch with content that doesn't exist in file
    patch = """diff --git a/example.py b/example.py
@@ -1,1 +1,1 @@
-THIS LINE DOES NOT EXIST
+new line
"""
    
    fixed_patch, metrics = validator.validate_and_fix_patch(patch, sample_file)
    
    # Should still return the patch, but with errors
    assert len(metrics['errors']) > 0
    assert any('not found' in err.lower() for err in metrics['errors'])


def test_multiple_hunks(validator, sample_file):
    """Test patch with multiple hunks."""
    patch = """diff --git a/example.py b/example.py
@@ -10,2 +10,1 @@
-import os
 import sys
@@ -20,1 +20,1 @@
-    print("Hello, World!")
+    print("Hello, Python!")
"""
    
    fixed_patch, metrics = validator.validate_and_fix_patch(patch, sample_file)
    
    # Should fix both hunks
    assert metrics['was_fixed']
    assert '@@ -1,' in fixed_patch  # First hunk fixed
    assert '@@ -5,' in fixed_patch or '@@ -4,' in fixed_patch  # Second hunk fixed


def test_get_metrics(validator, sample_file):
    """Test metrics tracking across multiple validations."""
    patch1 = """diff --git a/example.py b/example.py
@@ -1,1 +1,1 @@
-import os
+import sys
"""
    
    patch2 = """diff --git a/example.py b/example.py
@@ -99,1 +99,1 @@
-import os
+import sys
"""
    
    # First patch - already valid
    validator.validate_and_fix_patch(patch1, sample_file)
    
    # Second patch - needs fixing
    validator.validate_and_fix_patch(patch2, sample_file)
    
    metrics = validator.get_metrics()
    assert metrics['validated'] == 2
    assert metrics['fixed'] == 1
    assert metrics['already_valid'] == 1


def test_complex_multiline_change(validator, tmp_path):
    """Test fixing patch with multiline changes."""
    file_path = tmp_path / "complex.py"
    file_path.write_text("""def calculate(x, y):
    result = x + y
    return result

def main():
    value = calculate(5, 3)
    print(value)
""")
    
    # Corrupt patch with wrong line numbers
    patch = """diff --git a/complex.py b/complex.py
@@ -50,3 +50,4 @@
 def calculate(x, y):
-    result = x + y
-    return result
+    total = x + y
+    logger.info(f"Calculated: {total}")
+    return total
"""
    
    fixed_patch, metrics = validator.validate_and_fix_patch(patch, file_path)
    
    assert metrics['is_valid']
    assert metrics['was_fixed']
    assert '@@ -1,' in fixed_patch  # Fixed to line 1


def test_patch_with_only_additions(validator, sample_file):
    """Test patch that only adds lines (no deletions)."""
    patch = """diff --git a/example.py b/example.py
@@ -99,0 +99,1 @@
+import logging
 import sys
"""
    
    fixed_patch, metrics = validator.validate_and_fix_patch(patch, sample_file)
    
    # Should find 'import sys' and fix line number
    assert metrics['was_fixed']
    assert '@@ -2,' in fixed_patch or '@@ -1,' in fixed_patch


def test_patch_with_only_deletions(validator, sample_file):
    """Test patch that only deletes lines (no additions)."""
    patch = """diff --git a/example.py b/example.py
@@ -99,2 +99,1 @@
-import os
 import sys
"""
    
    fixed_patch, metrics = validator.validate_and_fix_patch(patch, sample_file)
    
    assert metrics['was_fixed']
    assert '@@ -1,' in fixed_patch  # Fixed to correct line


@pytest.mark.parametrize("wrong_line,expected_fixed", [
    (5, True),   # Wrong line number
    (10, True),  # Way off
    (100, True), # Very wrong
    (1, False),  # Already correct
])
def test_various_line_number_errors(validator, sample_file, wrong_line, expected_fixed):
    """Test fixing patches with various incorrect line numbers."""
    patch = f"""diff --git a/example.py b/example.py
@@ -{wrong_line},1 +{wrong_line},1 @@
-import os
+import sys
"""
    
    fixed_patch, metrics = validator.validate_and_fix_patch(patch, sample_file)
    
    assert metrics['was_fixed'] == expected_fixed
    if expected_fixed:
        assert '@@ -1,' in fixed_patch
