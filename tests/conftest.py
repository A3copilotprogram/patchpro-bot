"""Test configuration and fixtures."""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_ruff_data() -> list:
    """Sample Ruff JSON data for testing."""
    return [
        {
            "code": "F401",
            "message": "'os' imported but unused",
            "filename": "test_file.py",
            "location": {"row": 1, "column": 8},
            "end_location": {"row": 1, "column": 10},
            "fix": {
                "applicability": "automatic",
                "edits": [
                    {
                        "content": "",
                        "location": {"row": 1, "column": 1},
                        "end_location": {"row": 2, "column": 1}
                    }
                ]
            }
        },
        {
            "code": "E501",
            "message": "line too long (82 > 79 characters)",
            "filename": "test_file.py",
            "location": {"row": 5, "column": 80},
            "end_location": {"row": 5, "column": 82}
        }
    ]


@pytest.fixture
def sample_semgrep_data() -> list:
    """Sample Semgrep JSON data for testing."""
    return [
        {
            "check_id": "python.lang.security.audit.dangerous-subprocess-use",
            "path": "test_file.py",
            "start": {
                "start": {"line": 10, "col": 5, "offset": 150},
                "end": {"line": 10, "col": 25, "offset": 170}
            },
            "end": {
                "start": {"line": 10, "col": 5, "offset": 150},
                "end": {"line": 10, "col": 25, "offset": 170}
            },
            "extra": {
                "message": "Dangerous subprocess call detected",
                "metadata": {
                    "category": "security",
                    "confidence": "HIGH"
                },
                "severity": "ERROR",
                "lines": "subprocess.call(user_input, shell=True)"
            }
        }
    ]


@pytest.fixture
def sample_code_content() -> str:
    """Sample Python code content for testing."""
    return '''import os
import sys
import subprocess

def main():
    print("Hello world with a very long line that exceeds the maximum line length limit")
    
    user_input = input("Enter command: ")
    subprocess.call(user_input, shell=True)
    
    return 0

if __name__ == "__main__":
    main()
'''
