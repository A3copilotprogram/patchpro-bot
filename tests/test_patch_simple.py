"""
Simple test to validate patch generator API works.

This is a minimal test to establish baseline before expanding to full suite.
"""

import pytest
from pathlib import Path
from patchpro_bot.models import AnalysisFinding, CodeLocation, Severity
from patchpro_bot.agentic_patch_generator_v2 import AgenticPatchGeneratorV2
from patchpro_bot.llm.client import LLMClient
import subprocess
import tempfile


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary Git repository for patch testing."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True
    )
    
    return repo_dir


@pytest.fixture
def llm_client():
    """Create LLM client for testing."""
    return LLMClient()


@pytest.fixture
def patch_generator(temp_repo, llm_client):
    """Create patch generator instance."""
    return AgenticPatchGeneratorV2(
        llm_client=llm_client,
        repo_path=temp_repo,
        max_retries=3,
        enable_planning=True,
        enable_tracing=False  # Disable tracing for tests
    )


def create_finding(
    rule_id: str,
    message: str,
    file_path: str,
    line: int,
    severity: Severity = Severity.WARNING,
    tool: str = "ruff"
) -> AnalysisFinding:
    """Helper to create test finding."""
    return AnalysisFinding(
        rule_id=rule_id,
        message=message,
        tool=tool,
        severity=severity,
        location=CodeLocation(file=file_path, line=line, column=1),
        context="",
        fix_available=False
    )


@pytest.mark.asyncio
async def test_simple_unused_import(temp_repo, patch_generator):
    """Test LLM can fix a simple unused import.
    
    This is the simplest possible test to validate the API works.
    """
    # Create test file
    test_file = temp_repo / "example.py"
    test_file.write_text('''import os
import sys

def main():
    print("Hello")
''')
    
    # Git commit
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_repo,
        check=True,
        capture_output=True
    )
    
    # Create finding
    finding = create_finding(
        rule_id="F401",
        message="'os' imported but unused",
        file_path="example.py",
        line=1,
        severity=Severity.WARNING,
        tool="ruff"
    )
    
    # Generate patch
    result = await patch_generator.generate_patches([finding])
    
    # Validate result structure
    assert "patches" in result, "Result should contain 'patches' key"
    assert "success_rate" in result, "Result should contain 'success_rate'"
    assert "total_attempts" in result, "Result should contain 'total_attempts'"
    
    # Log results for debugging
    print(f"\n📊 Test Results:")
    print(f"  Success rate: {result['success_rate']:.1%}")
    print(f"  Total attempts: {result['total_attempts']}")
    print(f"  Patches generated: {len(result['patches'])}")
    print(f"  Memory: {result['memory']}")
    
    # We expect this to pass based on trace analysis
    # But if it fails, we want to see the details
    if result['patches']:
        print(f"\n✓ Generated {len(result['patches'])} patch(es)")
        print(f"  First patch type: {type(result['patches'][0])}")
    else:
        print(f"\n✗ No patches generated")
        print(f"  Failures: {result['failures']}")


@pytest.mark.asyncio
async def test_sql_injection_security_fix(temp_repo, patch_generator):
    """Test LLM can fix SQL injection vulnerability.
    
    Expected to pass based on trace analysis (75% success for security fixes).
    """
    # Create vulnerable file
    vuln_file = temp_repo / "vulnerable.py"
    vuln_file.write_text('''
import sqlite3

def get_user(username):
    conn = sqlite3.connect("users.db")
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return conn.execute(query).fetchone()
''')
    
    # Git commit
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_repo,
        check=True,
        capture_output=True
    )
    
    # Create finding
    finding = create_finding(
        rule_id="python.lang.security.audit.formatted-sql-query",
        message="SQL query formatted with string interpolation. Use parameterized queries.",
        file_path="vulnerable.py",
        line=6,
        severity=Severity.ERROR,
        tool="semgrep"
    )
    
    # Generate patch
    result = await patch_generator.generate_patches([finding])
    
    # Log results
    print(f"\n📊 SQL Injection Fix Results:")
    print(f"  Success rate: {result['success_rate']:.1%}")
    print(f"  Patches: {len(result['patches'])}")
    
    # Expect success for security fixes
    assert result['success_rate'] > 0, "Security fixes should have >0% success rate"
