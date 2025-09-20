"""Semgrep JSON output models."""

from typing import Optional, Any, Dict
from pydantic import BaseModel, Field

from .common import AnalysisFinding, CodeLocation, Severity


class SemgrepPosition(BaseModel):
    """Semgrep position information."""
    line: int = Field(..., description="Line number (1-indexed)")
    col: int = Field(..., description="Column number (1-indexed)")
    offset: Optional[int] = Field(None, description="Byte offset")


class SemgrepLocation(BaseModel):
    """Semgrep location range."""
    start: SemgrepPosition = Field(..., description="Start position")
    end: SemgrepPosition = Field(..., description="End position")


class SemgrepExtra(BaseModel):
    """Extra information from Semgrep."""
    message: Optional[str] = Field(None, description="Rule message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Rule metadata")
    severity: Optional[str] = Field(None, description="Rule severity")
    lines: Optional[str] = Field(None, description="Matched lines")
    fix: Optional[str] = Field(None, description="Suggested fix")


class SemgrepRawFinding(BaseModel):
    """Raw Semgrep finding as returned by semgrep JSON output."""
    check_id: str = Field(..., description="Rule ID")
    path: str = Field(..., description="File path")
    start: SemgrepLocation = Field(..., description="Finding location")
    end: SemgrepLocation = Field(..., description="Finding end location")
    extra: SemgrepExtra = Field(..., description="Extra information")
    
    
class SemgrepFinding(AnalysisFinding):
    """Semgrep finding converted to unified format."""
    
    @classmethod
    def from_raw(cls, raw: SemgrepRawFinding) -> "SemgrepFinding":
        """Convert raw Semgrep finding to unified format."""
        # Map Semgrep location to unified location
        location = CodeLocation(
            file=raw.path,
            line=raw.start.start.line,
            column=raw.start.start.col,
            end_line=raw.end.end.line,
            end_column=raw.end.end.col,
        )
        
        # Extract message
        message = raw.extra.message or f"Semgrep rule {raw.check_id} triggered"
        
        # Map severity
        severity = cls._map_severity(raw.extra.severity)
        
        # Extract suggested fix
        suggested_fix = raw.extra.fix
        
        # Extract code snippet if available
        code_snippet = raw.extra.lines
        
        # Get category from metadata
        category = None
        if raw.extra.metadata:
            category = raw.extra.metadata.get("category")
        
        # Get confidence from metadata
        confidence = None
        if raw.extra.metadata:
            confidence = raw.extra.metadata.get("confidence")
        
        return cls(
            tool="semgrep",
            rule_id=raw.check_id,
            rule_name=raw.extra.metadata.get("shortlink") if raw.extra.metadata else None,
            location=location,
            message=message,
            severity=severity,
            code_snippet=code_snippet,
            suggested_fix=suggested_fix,
            category=category,
            confidence=confidence,
        )
    
    @staticmethod
    def _map_severity(semgrep_severity: Optional[str]) -> Severity:
        """Map Semgrep severity to unified severity."""
        if not semgrep_severity:
            return Severity.INFO
        
        severity_map = {
            "ERROR": Severity.ERROR,
            "WARNING": Severity.WARNING,
            "INFO": Severity.INFO,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
        }
        
        return severity_map.get(semgrep_severity.upper(), Severity.INFO)
