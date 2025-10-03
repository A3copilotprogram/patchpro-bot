"""Common data models shared across analysis tools."""

from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for analysis findings."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CodeLocation(BaseModel):
    """Represents a location in source code."""
    file: str = Field(..., description="Path to the file")
    line: int = Field(..., description="Line number (1-indexed)")
    column: Optional[int] = Field(None, description="Column number (1-indexed)")
    end_line: Optional[int] = Field(None, description="End line number")
    end_column: Optional[int] = Field(None, description="End column number")


class AnalysisFinding(BaseModel):
    """Unified model for analysis findings from any tool."""
    
    # Core identification
    tool: str = Field(..., description="Tool that generated the finding (ruff, semgrep)")
    rule_id: str = Field(..., description="Rule or check identifier")
    rule_name: Optional[str] = Field(None, description="Human-readable rule name")
    
    # Location information
    location: CodeLocation = Field(..., description="Code location")
    
    # Finding details
    message: str = Field(..., description="Issue description")
    severity: Severity = Field(..., description="Severity level")
    
    # Code context
    code_snippet: Optional[str] = Field(None, description="Relevant code snippet")
    suggested_fix: Optional[str] = Field(None, description="Suggested fix if available")
    
    # Additional metadata
    category: Optional[str] = Field(None, description="Category of the issue")
    confidence: Optional[str] = Field(None, description="Confidence level")
    
    def __str__(self) -> str:
        """String representation of the finding."""
        return f"{self.tool}:{self.rule_id} at {self.location.file}:{self.location.line} - {self.message}"
