"""PatchPro Bot - CI code-repair assistant."""

from .agent_core import AgentCore, AgentConfig
from .analysis import AnalysisReader, FindingAggregator
from .llm import LLMClient, PromptBuilder, ResponseParser
from .diff import DiffGenerator, FileReader, PatchWriter
from .models import AnalysisFinding, RuffFinding, SemgrepFinding

"""PatchPro Bot - CI code-repair assistant."""

from .agent_core import AgentCore, AgentConfig
from .run_ci import main

__version__ = "0.0.1"
__all__ = ["AgentCore", "AgentConfig", "main"]