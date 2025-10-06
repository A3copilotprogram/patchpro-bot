#!/usr/bin/env python3
"""
Test Fixture Generator for PatchPro Unit Tests

Generates synthetic Python files with intentional code quality issues
and corresponding analysis findings for testing patch generation.

Usage:
    python scripts/generate_test_fixtures.py
    
This creates:
    tests/fixtures/security/     - Security vulnerability examples
    tests/fixtures/style/        - Style issue examples  
    tests/fixtures/imports/      - Import-related issues
    tests/fixtures/findings/     - Simulated analyzer outputs

Benefits:
    - No API calls needed (fast tests)
    - Repeatable test data
    - Comprehensive rule coverage
    - Easy to add new test cases
"""

import json
from pathlib import Path
from typing import List, Dict, Any

# Base directory for fixtures
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


def create_fixture_dirs():
    """Create fixture directory structure."""
    dirs = [
        FIXTURES_DIR / "security",
        FIXTURES_DIR / "style", 
        FIXTURES_DIR / "imports",
        FIXTURES_DIR / "findings",
    ]
    for dir in dirs:
        dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Created fixture directories in {FIXTURES_DIR}")


# =============================================================================
# Security Vulnerability Fixtures (HIGH SUCCESS RATE EXPECTED)
# =============================================================================

def generate_sql_injection_fixture():
    """Generate file with SQL injection vulnerability."""
    code = '''"""Example with SQL injection vulnerability."""
import sqlite3

def get_user(username):
    """Fetch user by username - VULNERABLE!"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # VULNERABLE: String concatenation in SQL query
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    
    return cursor.fetchone()

def get_user_safe(username):
    """Fetch user by username - SAFE."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # SAFE: Parameterized query
    query = "SELECT * FROM users WHERE username = ?"
    cursor.execute(query, (username,))
    
    return cursor.fetchone()
'''
    
    (FIXTURES_DIR / "security" / "sql_injection.py").write_text(code)
    
    # Generate corresponding finding
    finding = {
        "tool": "semgrep",
        "rule_id": "python.lang.security.audit.formatted-sql-query.formatted-sql-query",
        "severity": "high",
        "message": "Detected SQL statement that is tainted by user input. Use parameterized queries.",
        "file": "tests/fixtures/security/sql_injection.py",
        "line": 10,
        "column": 5,
        "end_line": 11,
        "end_column": 30,
        "code_snippet": '    query = f"SELECT * FROM users WHERE username = \'{username}\'"'
    }
    
    return finding


def generate_insecure_hash_fixture():
    """Generate file with insecure hash algorithm."""
    code = '''"""Example with insecure hash algorithm."""
import hashlib

def hash_password_insecure(password):
    """Hash password using SHA-1 - INSECURE!"""
    # VULNERABLE: SHA-1 is cryptographically broken
    return hashlib.sha1(password.encode()).hexdigest()

def hash_password_secure(password):
    """Hash password using SHA-256 - SECURE."""
    # SECURE: SHA-256 is cryptographically strong
    return hashlib.sha256(password.encode()).hexdigest()

def hash_password_best(password):
    """Hash password using bcrypt - BEST."""
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())
'''
    
    (FIXTURES_DIR / "security" / "insecure_hash.py").write_text(code)
    
    finding = {
        "tool": "semgrep",
        "rule_id": "python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1",
        "severity": "medium",
        "message": "SHA-1 is cryptographically broken. Use SHA-256 or better.",
        "file": "tests/fixtures/security/insecure_hash.py",
        "line": 7,
        "column": 12,
        "end_line": 7,
        "end_column": 58,
        "code_snippet": "    return hashlib.sha1(password.encode()).hexdigest()"
    }
    
    return finding


# =============================================================================
# Style Issue Fixtures (LOW SUCCESS RATE EXPECTED - MECHANICAL FIXES)
# =============================================================================

def generate_unused_variable_fixture():
    """Generate file with unused variable (F841)."""
    code = '''"""Example with unused variable."""

def calculate_total(items):
    """Calculate total price of items."""
    total = 0
    count = 0  # F841: Local variable 'count' is assigned but never used
    
    for item in items:
        total += item['price']
        # count should be used here but isn't
    
    return total

def calculate_total_fixed(items):
    """Calculate total price of items - FIXED."""
    total = 0
    # Removed unused 'count' variable
    
    for item in items:
        total += item['price']
    
    return total
'''
    
    (FIXTURES_DIR / "style" / "unused_variable.py").write_text(code)
    
    finding = {
        "tool": "ruff",
        "rule_id": "F841",
        "severity": "info",
        "message": "Local variable `count` is assigned to but never used",
        "file": "tests/fixtures/style/unused_variable.py",
        "line": 6,
        "column": 5,
        "end_line": 6,
        "end_column": 10,
        "code_snippet": "    count = 0  # F841: Local variable 'count' is assigned but never used"
    }
    
    return finding


def generate_multiple_imports_fixture():
    """Generate file with multiple imports on one line (E401)."""
    code = '''"""Example with multiple imports on one line."""
import os, sys, json  # E401: Multiple imports on one line

def process_data():
    """Process some data using imported modules."""
    data = json.loads('{"key": "value"}')
    print(f"Running on {sys.platform} in {os.getcwd()}")
    return data
'''
    
    (FIXTURES_DIR / "style" / "multiple_imports.py").write_text(code)
    
    finding = {
        "tool": "ruff",
        "rule_id": "E401",
        "severity": "info",
        "message": "Multiple imports on one line",
        "file": "tests/fixtures/style/multiple_imports.py",
        "line": 2,
        "column": 1,
        "end_line": 2,
        "end_column": 30,
        "code_snippet": "import os, sys, json  # E401: Multiple imports on one line"
    }
    
    return finding


# =============================================================================
# Import Issue Fixtures
# =============================================================================

def generate_unused_import_fixture():
    """Generate file with unused import (F401)."""
    code = '''"""Example with unused import."""
import os
import sys  # F401: 'sys' imported but unused
import json

def read_file(path):
    """Read file contents."""
    with open(path) as f:
        return json.load(f)

# Note: sys and os are imported but only json is used
'''
    
    (FIXTURES_DIR / "imports" / "unused_import.py").write_text(code)
    
    finding = {
        "tool": "ruff",
        "rule_id": "F401",
        "severity": "info",
        "message": "`sys` imported but unused",
        "file": "tests/fixtures/imports/unused_import.py",
        "line": 3,
        "column": 8,
        "end_line": 3,
        "end_column": 11,
        "code_snippet": "import sys  # F401: 'sys' imported but unused"
    }
    
    return finding


def generate_import_ordering_simple_fixture():
    """Generate simple file with import ordering issue (I001)."""
    code = '''"""Example with simple import ordering issue."""
import json
import os
import sys  # I001: Import block is not sorted

def main():
    """Main function."""
    print(f"Platform: {sys.platform}")
    print(f"CWD: {os.getcwd()}")
    data = json.dumps({"status": "ok"})
    return data
'''
    
    (FIXTURES_DIR / "imports" / "import_ordering_simple.py").write_text(code)
    
    finding = {
        "tool": "ruff",
        "rule_id": "I001",
        "severity": "info",
        "message": "Import block is not sorted",
        "file": "tests/fixtures/imports/import_ordering_simple.py",
        "line": 2,
        "column": 1,
        "end_line": 4,
        "end_column": 11,
        "code_snippet": "import json\nimport os\nimport sys"
    }
    
    return finding


def generate_import_ordering_complex_fixture():
    """Generate complex file with import ordering issue (I001)."""
    code = '''"""Example with complex import ordering issue."""
import json
import os
import sys
from pathlib import Path
from typing import Dict, List
import asyncio
from dataclasses import dataclass
import re
from collections import defaultdict

# Third-party imports mixed with stdlib
import requests
import pytest
from pydantic import BaseModel

@dataclass
class Config:
    """Configuration class."""
    api_key: str
    timeout: int
'''
    
    (FIXTURES_DIR / "imports" / "import_ordering_complex.py").write_text(code)
    
    finding = {
        "tool": "ruff",
        "rule_id": "I001",
        "severity": "info",
        "message": "Import block is not sorted or grouped correctly",
        "file": "tests/fixtures/imports/import_ordering_complex.py",
        "line": 2,
        "column": 1,
        "end_line": 14,
        "end_column": 30,
        "code_snippet": "# Complex import block with mixed stdlib and third-party"
    }
    
    return finding


# =============================================================================
# Generate All Fixtures
# =============================================================================

def generate_all_fixtures():
    """Generate all test fixtures."""
    print("Generating test fixtures...")
    print()
    
    # Create directories
    create_fixture_dirs()
    print()
    
    # Collect all findings
    findings = []
    
    # Security fixtures (HIGH SUCCESS EXPECTED)
    print("📝 Generating security fixtures (expect 50-75% success)...")
    findings.append(generate_sql_injection_fixture())
    print("  ✓ sql_injection.py")
    findings.append(generate_insecure_hash_fixture())
    print("  ✓ insecure_hash.py")
    print()
    
    # Style fixtures (LOW SUCCESS EXPECTED)
    print("📝 Generating style fixtures (expect 0-25% success - xfail)...")
    findings.append(generate_unused_variable_fixture())
    print("  ✓ unused_variable.py")
    findings.append(generate_multiple_imports_fixture())
    print("  ✓ multiple_imports.py")
    print()
    
    # Import fixtures (MIXED SUCCESS)
    print("📝 Generating import fixtures (expect 20-50% success)...")
    findings.append(generate_unused_import_fixture())
    print("  ✓ unused_import.py")
    findings.append(generate_import_ordering_simple_fixture())
    print("  ✓ import_ordering_simple.py (expect 30-50% success)")
    findings.append(generate_import_ordering_complex_fixture())
    print("  ✓ import_ordering_complex.py (expect 0-20% success - xfail)")
    print()
    
    # Save findings as JSON
    findings_file = FIXTURES_DIR / "findings" / "all_findings.json"
    findings_file.write_text(json.dumps(findings, indent=2))
    print(f"✓ Saved {len(findings)} findings to {findings_file}")
    print()
    
    # Generate README
    readme = '''# Test Fixtures for PatchPro Unit Tests

This directory contains synthetic test files with intentional code quality issues
for testing patch generation without requiring API calls or external dependencies.

## Structure

- `security/` - Security vulnerability examples (HIGH success rate expected: 50-75%)
- `style/` - Style issue examples (LOW success rate expected: 0-25%, marked xfail)
- `imports/` - Import-related issues (MIXED success rate: 20-50%)
- `findings/` - Simulated analyzer outputs (JSON)

## Usage in Tests

```python
from pathlib import Path
import json

# Load finding
fixtures_dir = Path(__file__).parent / "fixtures"
findings = json.loads((fixtures_dir / "findings" / "all_findings.json").read_text())

# Get specific finding
sql_injection_finding = next(f for f in findings if f["rule_id"].endswith("sql-query"))

# Use in test
def test_sql_injection_fix():
    finding = create_finding_from_fixture(sql_injection_finding)
    patch = generator.generate_single_patch(finding)
    assert can_apply_patch(patch)
```

## Regenerating Fixtures

If you need to update fixtures or add new ones:

```bash
python scripts/generate_test_fixtures.py
```

## Expected Success Rates (from TRACE_ANALYSIS.md)

| Category | Rules | Expected Success | Status |
|----------|-------|------------------|--------|
| Security | Semgrep | 50-75% | Should pass |
| Style | F841, E401 | 0-25% | xfail (known issue) |
| Imports (simple) | I001, F401 | 30-50% | Should mostly pass |
| Imports (complex) | I001 complex | 0-20% | xfail (known issue) |

## Adding New Fixtures

1. Add generator function in `scripts/generate_test_fixtures.py`
2. Return finding dict with: tool, rule_id, file, line, message
3. Run script to regenerate fixtures
4. Update tests to use new fixture
'''
    
    readme_file = FIXTURES_DIR / "README.md"
    readme_file.write_text(readme)
    print(f"✓ Created {readme_file}")
    print()
    
    print("=" * 80)
    print("✅ All fixtures generated successfully!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Update tests/test_patch_quality.py to use fixtures")
    print("2. Run tests: pytest tests/test_patch_quality.py -v")
    print("3. Establish baseline (~30% pass rate expected)")
    print()


if __name__ == "__main__":
    generate_all_fixtures()
