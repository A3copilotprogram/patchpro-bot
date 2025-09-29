
import pytest
from patchpro_bot.test_sample import (
    add_numbers,
    string_formatting_issues,
    performance_issues,
    security_issues,
    bad_exception_handling
)

def test_add_numbers():
    """Test add_numbers returns correct sum."""
    assert add_numbers(2, 3) == 5
    assert add_numbers(-1, 1) == 0

def test_string_formatting_issues():
    """Test string_formatting_issues returns correct message."""
    assert string_formatting_issues() == "Hello world"

def test_performance_issues():
    """Test performance_issues returns even numbers."""
    assert performance_issues() == [2, 4]

def test_security_issues():
    """Test security_issues returns expected tuple."""
    password, query = security_issues()
    assert password == "hardcoded_password123"
    assert "DROP TABLE" in query

def test_bad_exception_handling():
    """Test bad_exception_handling does not raise exception."""
    try:
        bad_exception_handling()
    except Exception:
        pytest.fail("bad_exception_handling() raised an exception!")
