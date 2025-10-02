"""PatchPro Bot - CI code-repair assistant."""

from .agent_core import AgentCore, AgentConfig, PromptStrategy
from .analysis import AnalysisReader, FindingAggregator
from .llm import LLMClient, PromptBuilder, ResponseParser, ResponseType
from .diff import DiffGenerator, FileReader, PatchWriter
from .models import AnalysisFinding, RuffFinding, SemgrepFinding
from .run_ci import main

__version__ = "9.9.9-CONFLICT"
from .test_sample import (
    add_numbers,
    string_formatting_issues,
    performance_issues,
    security_issues,
    bad_exception_handling,
)

__all__ = [
    "AgentCore", "AgentConfig", "PromptStrategy", "main",
    "AnalysisReader", "FindingAggregator",
    "LLMClient", "PromptBuilder", "ResponseParser", "ResponseType",
    "DiffGenerator", "FileReader", "PatchWriter",
    "AnalysisFinding", "RuffFinding", "SemgrepFinding",
    "add_numbers", "string_formatting_issues", "performance_issues", "security_issues", "bad_exception_handling",
    "CONFLICT_SYMBOL"
]

# BEGIN CONFLICT: Add a conflicting symbol
CONFLICT_SYMBOL = "This is a simulated export conflict!"
# END CONFLICT
