"""Ruff JSON output models."""

from typing import Optional, List
from pydantic import BaseModel, Field

from .common import AnalysisFinding, CodeLocation, Severity


class RuffLocation(BaseModel):
    """Ruff-specific location model."""
    row: int = Field(..., description="Line number (1-indexed)")
    column: int = Field(..., description="Column number (1-indexed)")


class RuffEdit(BaseModel):
    """Ruff edit suggestion."""
    content: str = Field(..., description="Replacement content")
    location: RuffLocation = Field(..., description="Edit location")
    end_location: Optional[RuffLocation] = Field(None, description="End location for edit")


class RuffFix(BaseModel):
    """Ruff fix information."""
    applicability: str = Field(..., description="Fix applicability (automatic, suggested, etc.)")
    message: Optional[str] = Field(None, description="Fix message")
    edits: List[RuffEdit] = Field(default_factory=list, description="Edit operations")


class RuffRawFinding(BaseModel):
    """Raw Ruff finding as returned by ruff JSON output."""
    code: str = Field(..., description="Rule code")
    message: str = Field(..., description="Issue message")
    filename: str = Field(..., description="File path")
    location: RuffLocation = Field(..., description="Issue location")
    end_location: Optional[RuffLocation] = Field(None, description="End location")
    fix: Optional[RuffFix] = Field(None, description="Fix information")
    url: Optional[str] = Field(None, description="Rule documentation URL")
    cell: Optional[str] = Field(None, description="Jupyter cell (if applicable)")
    
    
class RuffFinding(AnalysisFinding):
    """Ruff finding converted to unified format."""
    
    @classmethod
    def from_raw(cls, raw: RuffRawFinding) -> "RuffFinding":
        """Convert raw Ruff finding to unified format."""
        # Map Ruff location to unified location
        location = CodeLocation(
            file=raw.filename,
            line=raw.location.row,
            column=raw.location.column,
            end_line=raw.end_location.row if raw.end_location else None,
            end_column=raw.end_location.column if raw.end_location else None,
        )
        
        # Determine severity (Ruff doesn't provide explicit severity)
        # We'll infer based on rule code patterns
        severity = cls._infer_severity(raw.code)
        
        # Extract suggested fix if available
        suggested_fix = None
        if raw.fix and raw.fix.edits:
            # For now, just take the first edit content
            suggested_fix = raw.fix.edits[0].content
        
        return cls(
            tool="ruff",
            rule_id=raw.code,
            location=location,
            message=raw.message,
            severity=severity,
            suggested_fix=suggested_fix,
            category=cls._get_category(raw.code),
        )
    
    @staticmethod
    def _infer_severity(rule_code: str) -> Severity:
        """Infer severity based on Ruff rule code."""
        # Error codes that typically indicate errors
        error_prefixes = {"E", "F", "S", "B"}  # Pycodestyle, Pyflakes, Security, Bugbear
        warning_prefixes = {"W", "C", "N", "D"}  # Warnings, Complexity, Naming, Docstrings
        
        prefix = rule_code[0] if rule_code else ""
        
        if prefix in error_prefixes:
            return Severity.ERROR
        elif prefix in warning_prefixes:
            return Severity.WARNING
        else:
            return Severity.INFO
    
    @staticmethod 
    def _get_category(rule_code: str) -> str:
        """Get category based on Ruff rule code prefix."""
        category_map = {
            "E": "style",
            "W": "style", 
            "F": "error",
            "C": "complexity",
            "N": "naming",
            "D": "documentation",
            "S": "security",
            "B": "bugbear",
            "A": "builtins",
            "T": "print",
            "I": "import",
        }
        
        prefix = rule_code[0] if rule_code else ""
        return category_map.get(prefix, "other")
