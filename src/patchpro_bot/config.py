"""Configuration management for PatchPro local development."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import tomllib
from dataclasses import dataclass, field


@dataclass
class RuffConfig:
    """Ruff-specific configuration."""
    config_file: Optional[str] = None
    select: List[str] = field(default_factory=lambda: ["E", "F", "W"])
    ignore: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    line_length: int = 88
    target_version: str = "py312"


@dataclass 
class SemgrepConfig:
    """Semgrep-specific configuration."""
    config: Optional[str] = None
    rules: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class LLMConfig:
    """LLM-specific configuration."""
    model: str = "gpt-4o-mini"
    max_tokens: int = 4000
    temperature: float = 0.1
    api_key_env: str = "OPENAI_API_KEY"


@dataclass
class OutputConfig:
    """Output configuration."""
    artifacts_dir: str = ".patchpro"
    format: str = "json"
    include_patches: bool = True
    verbose: bool = False


@dataclass
class AnalysisConfig:
    """Analysis configuration."""
    tools: List[str] = field(default_factory=lambda: ["ruff", "semgrep"])
    exclude_patterns: List[str] = field(default_factory=lambda: ["tests/", "__pycache__/", ".venv/"])
    max_findings_per_file: int = 50
    severity_threshold: str = "info"  # info, warning, error


@dataclass
class AgentConfig:
    """Agent-specific configuration (agentic mode, telemetry)."""
    enable_agentic_mode: bool = False
    agentic_max_retries: int = 3
    agentic_enable_planning: bool = True
    enable_tracing: bool = True


@dataclass
class PatchProConfig:
    """Main PatchPro configuration."""
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    ruff: RuffConfig = field(default_factory=RuffConfig)
    semgrep: SemgrepConfig = field(default_factory=SemgrepConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "PatchProConfig":
        """Load configuration from file or use defaults."""
        if config_path is None:
            # Look for config in current directory and parents
            current = Path.cwd()
            for parent in [current] + list(current.parents):
                config_file = parent / ".patchpro.toml"
                if config_file.exists():
                    config_path = config_file
                    break
        
        if config_path and config_path.exists():
            return cls._load_from_file(config_path)
        else:
            return cls()  # Use defaults
    
    @classmethod
    def _load_from_file(cls, config_path: Path) -> "PatchProConfig":
        """Load configuration from TOML file."""
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            
            # Parse sections
            config = cls()
            
            if "analysis" in data:
                analysis_data = data["analysis"]
                config.analysis = AnalysisConfig(
                    tools=analysis_data.get("tools", config.analysis.tools),
                    exclude_patterns=analysis_data.get("exclude_patterns", config.analysis.exclude_patterns),
                    max_findings_per_file=analysis_data.get("max_findings_per_file", config.analysis.max_findings_per_file),
                    severity_threshold=analysis_data.get("severity_threshold", config.analysis.severity_threshold),
                )
            
            if "ruff" in data:
                ruff_data = data["ruff"]
                config.ruff = RuffConfig(
                    config_file=ruff_data.get("config_file"),
                    select=ruff_data.get("select", config.ruff.select),
                    ignore=ruff_data.get("ignore", config.ruff.ignore),
                    exclude=ruff_data.get("exclude", config.ruff.exclude),
                    line_length=ruff_data.get("line_length", config.ruff.line_length),
                    target_version=ruff_data.get("target_version", config.ruff.target_version),
                )
            
            if "semgrep" in data:
                semgrep_data = data["semgrep"]
                config.semgrep = SemgrepConfig(
                    config=semgrep_data.get("config"),
                    rules=semgrep_data.get("rules", config.semgrep.rules),
                    exclude=semgrep_data.get("exclude", config.semgrep.exclude),
                )
            
            if "llm" in data:
                llm_data = data["llm"]
                config.llm = LLMConfig(
                    model=llm_data.get("model", config.llm.model),
                    max_tokens=llm_data.get("max_tokens", config.llm.max_tokens),
                    temperature=llm_data.get("temperature", config.llm.temperature),
                    api_key_env=llm_data.get("api_key_env", config.llm.api_key_env),
                )
            
            if "output" in data:
                output_data = data["output"]
                config.output = OutputConfig(
                    artifacts_dir=output_data.get("artifacts_dir", config.output.artifacts_dir),
                    format=output_data.get("format", config.output.format),
                    include_patches=output_data.get("include_patches", config.output.include_patches),
                    verbose=output_data.get("verbose", config.output.verbose),
                )
            
            if "agent" in data:
                agent_data = data["agent"]
                config.agent = AgentConfig(
                    enable_agentic_mode=agent_data.get("enable_agentic_mode", config.agent.enable_agentic_mode),
                    agentic_max_retries=agent_data.get("agentic_max_retries", config.agent.agentic_max_retries),
                    agentic_enable_planning=agent_data.get("agentic_enable_planning", config.agent.agentic_enable_planning),
                    enable_tracing=agent_data.get("enable_tracing", config.agent.enable_tracing),
                )
            
            return config
            
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
            return cls()  # Fall back to defaults
    
    def save(self, config_path: Path) -> None:
        """Save configuration to TOML file."""
        config_data = {
            "analysis": {
                "tools": self.analysis.tools,
                "exclude_patterns": self.analysis.exclude_patterns,
                "max_findings_per_file": self.analysis.max_findings_per_file,
                "severity_threshold": self.analysis.severity_threshold,
            },
            "ruff": {
                "config_file": self.ruff.config_file,
                "select": self.ruff.select,
                "ignore": self.ruff.ignore,
                "exclude": self.ruff.exclude,
                "line_length": self.ruff.line_length,
                "target_version": self.ruff.target_version,
            },
            "semgrep": {
                "config": self.semgrep.config,
                "rules": self.semgrep.rules,
                "exclude": self.semgrep.exclude,
            },
            "llm": {
                "model": self.llm.model,
                "max_tokens": self.llm.max_tokens,
                "temperature": self.llm.temperature,
                "api_key_env": self.llm.api_key_env,
            },
            "output": {
                "artifacts_dir": self.output.artifacts_dir,
                "format": self.output.format,
                "include_patches": self.output.include_patches,
                "verbose": self.output.verbose,
            },
            "agent": {
                "enable_agentic_mode": self.agent.enable_agentic_mode,
                "agentic_max_retries": self.agent.agentic_max_retries,
                "agentic_enable_planning": self.agent.agentic_enable_planning,
                "enable_tracing": self.agent.enable_tracing,
            },
        }
        
        import tomli_w
        with open(config_path, "wb") as f:
            tomli_w.dump(config_data, f)


def create_default_config(project_path: Path) -> Path:
    """Create a default .patchpro.toml configuration file."""
    config_path = project_path / ".patchpro.toml"
    config = PatchProConfig()
    config.save(config_path)
    return config_path


def find_config_file(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find .patchpro.toml in current directory or parents."""
    if start_path is None:
        start_path = Path.cwd()
    
    for parent in [start_path] + list(start_path.parents):
        config_file = parent / ".patchpro.toml"
        if config_file.exists():
            return config_file
    
    return None