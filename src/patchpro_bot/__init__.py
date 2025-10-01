"""PatchPro Bot - CI code-repair assistant."""

from .agent_core import AgentCore, AgentConfig, PromptStrategy
from .analysis import AnalysisReader, FindingAggregator
from .llm import LLMClient, PromptBuilder, ResponseParser, ResponseType
from .diff import DiffGenerator, FileReader, PatchWriter
from .models import AnalysisFinding, RuffFinding, SemgrepFinding
from .run_ci import main

__version__ = "0.0.1"
__all__ = [
	"AgentCore", "AgentConfig", "PromptStrategy", "main",
	"AnalysisReader", "FindingAggregator",
	"LLMClient", "PromptBuilder", "ResponseParser", "ResponseType",
	"DiffGenerator", "FileReader", "PatchWriter",
	"AnalysisFinding", "RuffFinding", "SemgrepFinding"
]
