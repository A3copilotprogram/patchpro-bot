"""Semgrep JSON output models."""

from typing import Optional, Any, Dict, Union
from pydantic import BaseModel, Field, field_validator

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
    start: Union[SemgrepLocation, Dict[str, Any]] = Field(..., description="Finding location")
    end: Union[SemgrepLocation, Dict[str, Any]] = Field(..., description="Finding end location")
    extra: SemgrepExtra = Field(..., description="Extra information")
    
    @field_validator('start', 'end', mode='before')
    @classmethod
    def parse_location(cls, v):
        """Parse location that can be nested or flat format."""
        if isinstance(v, dict):
            # Handle flat format: {"line": X, "col": Y, "offset": Z}
            if "line" in v and "col" in v and "start" not in v:
                pos = SemgrepPosition(line=v["line"], col=v["col"], offset=v.get("offset"))
                return SemgrepLocation(start=pos, end=pos)
            # Handle nested format: {"start": {"line": X, "col": Y}, "end": {...}}
            elif "start" in v and "end" in v:
                start_pos = SemgrepPosition(**v["start"])
                end_pos = SemgrepPosition(**v["end"])
                return SemgrepLocation(start=start_pos, end=end_pos)
        return v
    
    
class SemgrepFinding(AnalysisFinding):
    """Semgrep finding converted to unified format."""
    
    @classmethod
    def from_raw(cls, raw: SemgrepRawFinding) -> "SemgrepFinding":
        """Convert raw Semgrep finding to unified format."""
        # Handle both nested and flat location formats
        if isinstance(raw.start, SemgrepLocation):
            start_line = raw.start.start.line
            start_col = raw.start.start.col
        else:
            # Fallback for flat format
            start_line = raw.start.get("line", 1)
            start_col = raw.start.get("col", 1)
            
        if isinstance(raw.end, SemgrepLocation):
            end_line = raw.end.end.line
            end_col = raw.end.end.col
        else:
            # Fallback for flat format
            end_line = raw.end.get("line", start_line)
            end_col = raw.end.get("col", start_col)
        
        # Map Semgrep location to unified location
        location = CodeLocation(
            file=raw.path,
            line=start_line,
            column=start_col,
            end_line=end_line,
            end_column=end_col,
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
