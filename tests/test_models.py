"""Tests for models module."""

import pytest
from pydantic import ValidationError

from patchpro_bot.models import (
    AnalysisFinding, RuffFinding, SemgrepFinding,
    CodeLocation, Severity
)
from patchpro_bot.models.ruff import RuffRawFinding
from patchpro_bot.models.semgrep import SemgrepRawFinding


class TestCodeLocation:
    """Tests for CodeLocation model."""
    
    def test_basic_location(self):
        """Test basic location creation."""
        location = CodeLocation(file="test.py", line=10, column=5)
        assert location.file == "test.py"
        assert location.line == 10
        assert location.column == 5
        assert location.end_line is None
        assert location.end_column is None
    
    def test_location_with_range(self):
        """Test location with end positions."""
        location = CodeLocation(
            file="test.py", 
            line=10, 
            column=5,
            end_line=12,
            end_column=15
        )
        assert location.end_line == 12
        assert location.end_column == 15


class TestAnalysisFinding:
    """Tests for AnalysisFinding model."""
    
    def test_basic_finding(self):
        """Test basic finding creation."""
        location = CodeLocation(file="test.py", line=10)
        finding = AnalysisFinding(
            tool="ruff",
            rule_id="F401",
            location=location,
            message="Unused import",
            severity=Severity.ERROR
        )
        
        assert finding.tool == "ruff"
        assert finding.rule_id == "F401"
        assert finding.message == "Unused import"
        assert finding.severity == Severity.ERROR
        assert finding.location.file == "test.py"
    
    def test_finding_string_representation(self):
        """Test string representation of finding."""
        location = CodeLocation(file="test.py", line=10)
        finding = AnalysisFinding(
            tool="ruff",
            rule_id="F401",
            location=location,
            message="Unused import",
            severity=Severity.ERROR
        )
        
        expected = "ruff:F401 at test.py:10 - Unused import"
        assert str(finding) == expected


class TestRuffFinding:
    """Tests for RuffFinding model."""
    
    def test_from_raw_basic(self, sample_ruff_data):
        """Test conversion from raw Ruff data."""
        raw_data = sample_ruff_data[0]
        raw_finding = RuffRawFinding.model_validate(raw_data)
        finding = RuffFinding.from_raw(raw_finding)
        
        assert finding.tool == "ruff"
        assert finding.rule_id == "F401"
        assert finding.message == "'os' imported but unused"
        assert finding.severity == Severity.ERROR  # F codes are errors
        assert finding.location.file == "test_file.py"
        assert finding.location.line == 1
        assert finding.location.column == 8
        assert finding.suggested_fix == ""  # From the fix edit
    
    def test_from_raw_no_fix(self, sample_ruff_data):
        """Test conversion from raw Ruff data without fix."""
        raw_data = sample_ruff_data[1]  # E501 without fix
        raw_finding = RuffRawFinding.model_validate(raw_data)
        finding = RuffFinding.from_raw(raw_finding)
        
        assert finding.tool == "ruff"
        assert finding.rule_id == "E501"
        assert finding.severity == Severity.ERROR  # E codes are errors
        assert finding.suggested_fix is None
    
    def test_severity_inference(self):
        """Test severity inference from rule codes."""
        assert RuffFinding._infer_severity("F401") == Severity.ERROR
        assert RuffFinding._infer_severity("E501") == Severity.ERROR
        assert RuffFinding._infer_severity("W293") == Severity.WARNING
        assert RuffFinding._infer_severity("C901") == Severity.WARNING
        assert RuffFinding._infer_severity("N803") == Severity.WARNING
        assert RuffFinding._infer_severity("D100") == Severity.WARNING
        assert RuffFinding._infer_severity("X999") == Severity.INFO
    
    def test_category_mapping(self):
        """Test category mapping from rule codes."""
        assert RuffFinding._get_category("F401") == "error"
        assert RuffFinding._get_category("E501") == "style"
        assert RuffFinding._get_category("W293") == "style"
        assert RuffFinding._get_category("C901") == "complexity"
        assert RuffFinding._get_category("N803") == "naming"
        assert RuffFinding._get_category("D100") == "documentation"
        assert RuffFinding._get_category("S101") == "security"
        assert RuffFinding._get_category("B007") == "bugbear"
        assert RuffFinding._get_category("X999") == "other"


class TestSemgrepFinding:
    """Tests for SemgrepFinding model."""
    
    def test_from_raw_basic(self, sample_semgrep_data):
        """Test conversion from raw Semgrep data."""
        raw_data = sample_semgrep_data[0]
        raw_finding = SemgrepRawFinding.model_validate(raw_data)
        finding = SemgrepFinding.from_raw(raw_finding)
        
        assert finding.tool == "semgrep"
        assert finding.rule_id == "python.lang.security.audit.dangerous-subprocess-use"
        assert finding.message == "Dangerous subprocess call detected"
        assert finding.severity == Severity.ERROR
        assert finding.location.file == "test_file.py"
        assert finding.location.line == 10
        assert finding.location.column == 5
        assert finding.category == "security"
        assert finding.confidence == "HIGH"
        assert "subprocess.call" in finding.code_snippet
    
    def test_severity_mapping(self):
        """Test severity mapping from Semgrep severities."""
        assert SemgrepFinding._map_severity("ERROR") == Severity.ERROR
        assert SemgrepFinding._map_severity("WARNING") == Severity.WARNING
        assert SemgrepFinding._map_severity("INFO") == Severity.INFO
        assert SemgrepFinding._map_severity("HIGH") == Severity.HIGH
        assert SemgrepFinding._map_severity("MEDIUM") == Severity.MEDIUM
        assert SemgrepFinding._map_severity("LOW") == Severity.LOW
        assert SemgrepFinding._map_severity("UNKNOWN") == Severity.INFO
        assert SemgrepFinding._map_severity(None) == Severity.INFO


class TestSeverity:
    """Tests for Severity enum."""
    
    def test_severity_values(self):
        """Test severity enum values."""
        assert Severity.ERROR.value == "error"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"
