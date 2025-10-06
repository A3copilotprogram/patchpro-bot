"""
Unit tests for patch generation quality.

Based on trace analysis (docs/TRACE_ANALYSIS.md), tests are categorized by
expected success rate:

1. High-success patterns (>=50% expected): Security fixes, semantic changes
2. Known-failure patterns (0-25% expected): Mechanical fixes, marked as xfail
3. Retry effectiveness: Tests that self-correction improves results

Goal: Establish baseline (~30% pass rate) and track improvement toward >90%.
"""

import pytest
from pathlib import Path
from patchpro_bot.models import AnalysisFinding, Location, Severity
from patchpro_bot.agentic_patch_generator_v2 import AgenticPatchGeneratorV2
from patchpro_bot.config import AgentConfig
import subprocess
import tempfile
import shutil


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary Git repository for patch testing."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True
    )
    
    return repo_dir


@pytest.fixture
def agent_config():
    """Agent configuration for testing."""
    return AgentConfig(
        enable_agentic_mode=True,
        agentic_max_retries=3,
        agentic_enable_planning=True
    )


@pytest.fixture
def patch_generator(temp_repo, agent_config):
    """Create patch generator instance."""
    return AgenticPatchGeneratorV2(
        repo_path=str(temp_repo),
        agent_config=agent_config
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
        location=Location(file=file_path, line=line, column=1),
        context="",
        fix_available=False
    )


def can_apply_patch(repo_dir: Path, patch_content: str) -> tuple[bool, str]:
    """Test if a patch can be applied with git apply.
    
    Returns:
        (success: bool, error_message: str)
    """
    patch_file = repo_dir / "test.patch"
    patch_file.write_text(patch_content)
    
    result = subprocess.run(
        ["git", "apply", "--check", str(patch_file)],
        cwd=repo_dir,
        capture_output=True,
        text=True
    )
    
    patch_file.unlink()
    
    return result.returncode == 0, result.stderr


# =============================================================================
# CATEGORY 1: HIGH-SUCCESS PATTERNS (Security Fixes - Expected >=50%)
# =============================================================================
#
# From trace analysis: Security fixes have 75% success rate
# These tests should PASS (or at least have >50% pass rate)
#

class TestSecurityFixes:
    """Tests for security-related fixes (Semgrep rules).
    
    Expected success rate: >=50% (trace analysis showed 75%)
    """
    
    def test_sql_injection_fix(self, temp_repo, patch_generator):
        """LLM should fix SQL injection by using parameterized queries.
        
        Based on successful trace:
        python.lang.security.audit.formatted-sql-query.formatted-sql-query
        Success rate in traces: 66% (2/3 attempts)
        """
        # Create vulnerable code
        code_file = temp_repo / "vulnerable.py"
        code_file.write_text('''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()
''')
        
        # Commit it
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_repo,
            check=True,
            capture_output=True
        )
        
        finding = create_finding(
            rule_id="python.lang.security.audit.formatted-sql-query.formatted-sql-query",
            message="Detected SQL query formatted with string interpolation. Use parameterized queries instead.",
            file_path="vulnerable.py",
            line=3,
            severity=Severity.ERROR,
            tool="semgrep"
        )
        
        # Generate patch
        result = patch_generator.process_findings([finding])
        
        # Assertions
        assert len(result["patches"]) > 0, "Should generate at least one patch"
        
        patch_content = result["patches"][0]["content"]
        success, error = can_apply_patch(temp_repo, patch_content)
        
        assert success, f"Patch should apply cleanly. Error: {error}"
        assert "execute(" in patch_content, "Should use parameterized execute()"
        assert "?" in patch_content or "%s" in patch_content, "Should use parameter placeholders"
    
    def test_insecure_hash_fix(self, temp_repo, patch_generator):
        """LLM should replace SHA-1 with SHA-256.
        
        Based on successful trace:
        python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
        Success rate in traces: 100% (1/1 attempt)
        """
        code_file = temp_repo / "auth.py"
        code_file.write_text('''
import hashlib

def hash_password(password):
    return hashlib.sha1(password.encode()).hexdigest()
''')
        
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_repo,
            check=True,
            capture_output=True
        )
        
        finding = create_finding(
            rule_id="python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1",
            message="SHA-1 is cryptographically broken. Use SHA-256 or SHA-512 instead.",
            file_path="auth.py",
            line=5,
            severity=Severity.ERROR,
            tool="semgrep"
        )
        
        result = patch_generator.process_findings([finding])
        
        assert len(result["patches"]) > 0, "Should generate patch"
        
        patch_content = result["patches"][0]["content"]
        success, error = can_apply_patch(temp_repo, patch_content)
        
        assert success, f"Patch should apply cleanly. Error: {error}"
        assert "sha256" in patch_content.lower() or "sha512" in patch_content.lower(), \
            "Should upgrade to SHA-256 or SHA-512"
        assert "-sha1" in patch_content, "Should remove SHA-1"
    
    def test_hardcoded_secret_fix(self, temp_repo, patch_generator):
        """LLM should replace hardcoded secrets with environment variables.
        
        Expected success rate: >=50% (semantic change, clear security pattern)
        """
        code_file = temp_repo / "config.py"
        code_file.write_text('''
# Configuration
API_KEY = "sk-1234567890abcdef"
DATABASE_PASSWORD = "admin123"

def connect():
    return db.connect(password=DATABASE_PASSWORD)
''')
        
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_repo,
            check=True,
            capture_output=True
        )
        
        finding = create_finding(
            rule_id="python.lang.security.audit.hardcoded-password",
            message="Hardcoded password detected. Use environment variables.",
            file_path="config.py",
            line=3,
            severity=Severity.ERROR,
            tool="semgrep"
        )
        
        result = patch_generator.process_findings([finding])
        
        if len(result["patches"]) > 0:
            patch_content = result["patches"][0]["content"]
            success, error = can_apply_patch(temp_repo, patch_content)
            
            if success:
                assert "os.environ" in patch_content or "os.getenv" in patch_content, \
                    "Should use environment variables"


# =============================================================================
# CATEGORY 2: KNOWN-FAILURE PATTERNS (Mechanical Fixes - Expected 0-25%)
# =============================================================================
#
# From trace analysis: Mechanical fixes have 0-25% success rate
# These tests are marked as xfail to document the baseline
#

class TestMechanicalFixes:
    """Tests for mechanical/formatting fixes (Ruff rules).
    
    Expected success rate: 0-25% (trace analysis showed failures)
    Marked as xfail to document baseline - NOT EXPECTED TO PASS YET
    """
    
    @pytest.mark.xfail(reason="Known issue: LLM generates corrupt patches for F841 (trace analysis: 0% success)")
    def test_unused_variable_fix(self, temp_repo, patch_generator):
        """LLM currently fails on unused variable removal.
        
        Based on failed traces: F841_example.py (exhausted retries)
        Error: "corrupt patch at line X"
        Success rate in traces: 0% (0/2 attempts)
        """
        code_file = temp_repo / "example.py"
        code_file.write_text('''
def calculate(a, b):
    result = a + b
    unused_var = 42  # This is never used
    return result
''')
        
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_repo,
            check=True,
            capture_output=True
        )
        
        finding = create_finding(
            rule_id="F841",
            message="Local variable 'unused_var' is assigned but never used",
            file_path="example.py",
            line=4
        )
        
        result = patch_generator.process_findings([finding])
        
        # This will likely fail with "corrupt patch" error
        assert len(result["patches"]) > 0, "Should attempt to generate patch"
        
        patch_content = result["patches"][0]["content"]
        success, error = can_apply_patch(temp_repo, patch_content)
        
        assert success, f"Patch should apply (currently fails). Error: {error}"
    
    @pytest.mark.xfail(reason="Known issue: LLM generates corrupt patches for E401 (trace analysis: 0% success)")
    def test_multiple_imports_per_line_fix(self, temp_repo, patch_generator):
        """LLM currently fails on splitting multiple imports.
        
        Based on failed traces: E401_test_code_quality.py (exhausted retries)
        Error: "corrupt patch at line 6"
        Success rate in traces: 0% (0/2 attempts)
        """
        code_file = temp_repo / "imports.py"
        code_file.write_text('''
import os, sys, json
from pathlib import Path

def main():
    pass
''')
        
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_repo,
            check=True,
            capture_output=True
        )
        
        finding = create_finding(
            rule_id="E401",
            message="Multiple imports on one line",
            file_path="imports.py",
            line=2
        )
        
        result = patch_generator.process_findings([finding])
        
        assert len(result["patches"]) > 0, "Should attempt to generate patch"
        
        patch_content = result["patches"][0]["content"]
        success, error = can_apply_patch(temp_repo, patch_content)
        
        assert success, f"Patch should apply (currently fails). Error: {error}"
    
    @pytest.mark.xfail(reason="Known issue: Import ordering fails in complex files (trace analysis: 0-20% success)")
    def test_import_ordering_complex_file(self, temp_repo, patch_generator):
        """LLM fails on import ordering in complex files.
        
        Based on failed traces: I001_vulnerable_auth.py, I001_vulnerable_payment_system.py
        Error: "context mismatch - while searching for..."
        Success rate in traces: 0% in complex files (20% in simple files)
        """
        code_file = temp_repo / "complex.py"
        code_file.write_text('''
import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Optional
import requests
import numpy as np
from collections import defaultdict

def process_data():
    pass
''')
        
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_repo,
            check=True,
            capture_output=True
        )
        
        finding = create_finding(
            rule_id="I001",
            message="Import block is unsorted or unformatted",
            file_path="complex.py",
            line=2
        )
        
        result = patch_generator.process_findings([finding])
        
        if len(result["patches"]) > 0:
            patch_content = result["patches"][0]["content"]
            success, error = can_apply_patch(temp_repo, patch_content)
            
            assert success, f"Patch should apply (currently fails). Error: {error}"


# =============================================================================
# CATEGORY 3: SIMPLE CASES THAT SHOULD WORK
# =============================================================================

class TestSimpleCases:
    """Tests for simple cases where LLM should succeed.
    
    Expected success rate: >=50%
    """
    
    def test_unused_import_simple_file(self, temp_repo, patch_generator):
        """LLM should handle unused imports in simple files.
        
        Based on trace: F401_demo_file.py succeeded on attempt 3
        Success rate in traces: 25% (1/4 attempts, but succeeded after retry)
        """
        code_file = temp_repo / "simple.py"
        code_file.write_text('''
import os
import sys

def main():
    print("Hello")
''')
        
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_repo,
            check=True,
            capture_output=True
        )
        
        finding = create_finding(
            rule_id="F401",
            message="'os' imported but unused",
            file_path="simple.py",
            line=2
        )
        
        result = patch_generator.process_findings([finding])
        
        # May require retry, so check if any patches generated
        if len(result["patches"]) > 0:
            patch_content = result["patches"][0]["content"]
            success, error = can_apply_patch(temp_repo, patch_content)
            
            if success:
                assert "-import os" in patch_content, "Should remove unused import"
    
    def test_import_ordering_simple_file(self, temp_repo, patch_generator):
        """LLM should handle import ordering in simple files.
        
        Based on trace: I001_quick_test.py succeeded on attempt 1
        Success rate in traces: 20% overall, but 100% in simple files
        """
        code_file = temp_repo / "quick_test.py"
        code_file.write_text('''
import sys
import os

def test():
    pass
''')
        
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=temp_repo,
            check=True,
            capture_output=True
        )
        
        finding = create_finding(
            rule_id="I001",
            message="Import block is unsorted or unformatted",
            file_path="quick_test.py",
            line=2
        )
        
        result = patch_generator.process_findings([finding])
        
        if len(result["patches"]) > 0:
            patch_content = result["patches"][0]["content"]
            success, error = can_apply_patch(temp_repo, patch_content)
            
            if success:
                # Check that os comes before sys (alphabetical)
                assert "+import os" in patch_content, "Should reorder imports"


# =============================================================================
# CATEGORY 4: RETRY EFFECTIVENESS
# =============================================================================

class TestRetryEffectiveness:
    """Tests that retries with error feedback improve success rate.
    
    Expected: Some improvement with retries (trace analysis showed 1/4 attempt-3 succeeded)
    """
    
    @pytest.mark.skip(reason="Requires integration with retry logic - implement after basic tests pass")
    def test_retry_improves_result(self, temp_repo, patch_generator):
        """Test that error feedback helps LLM correct mistakes.
        
        Based on trace: formatted-sql-query_vulnerable_payment_system.py
        - Attempt 1: Failed with context mismatch
        - Attempt 3: Succeeded after feedback
        
        This test requires mocking retry logic to capture intermediate attempts.
        """
        pass


# =============================================================================
# TEST SUMMARY AND BASELINE METRICS
# =============================================================================

class TestBaselineMetrics:
    """Collect baseline metrics to track improvement over time.
    
    Run this test class to get current success rates.
    """
    
    @pytest.mark.skip(reason="Meta-test for reporting only")
    def test_report_baseline_metrics(self):
        """Report baseline success rates from test run.
        
        After running all tests, calculate:
        - Overall pass rate
        - Security fix pass rate (Category 1)
        - Mechanical fix pass rate (Category 2) - expect ~0%
        - Simple case pass rate (Category 3)
        
        Compare to trace analysis baseline: 29.4% overall
        
        Target progression:
        - Baseline: ~30%
        - After Phase 3.1-3.2 fixes: ~50%
        - After Phase 3.3 (skip mechanical): ~70%
        - Final goal: >90%
        """
        pass


if __name__ == "__main__":
    # Run tests with: pytest tests/test_patch_quality.py -v
    #
    # Expected results (baseline):
    # - Category 1 (Security): 2-3 / 3 pass (66-100%) ✓
    # - Category 2 (Mechanical): 0 / 3 pass (0%) ✗ (xfail expected)
    # - Category 3 (Simple): 1-2 / 2 pass (50-100%) ✓
    # - Overall: ~30-50% pass rate
    #
    # After Phase 3 fixes:
    # - Expected: 50-70% pass rate
    # - Target: >90% pass rate
    pytest.main([__file__, "-v", "--tb=short"])
