"""
Analyzer module for normalizing static analysis findings from Ruff, Semgrep and other tools.

This module provides normalization of findings from multiple static analysis tools
into a unified schema, with proper path normalization relative to git root.

Key features:
- Normalizes findings from ruff and semgrep
- Converts absolute paths to relative paths from git root
- Provides unified Finding schema for downstream processing
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum


class Severity(Enum):
    """Normalized severity levels for findings across all tools."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    NOTE = "note"


class Category(Enum):
    """Finding categories."""
    STYLE = "style"
    SECURITY = "security"
    PERFORMANCE = "performance"
    CORRECTNESS = "correctness"
    COMPLEXITY = "complexity"
    IMPORT = "import"
    TYPING = "typing"


@dataclass
class Position:
    """Position in source code."""
    line: int
    column: int


@dataclass
class Location:
    """Location of a finding in source code."""
    file: str
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None


@dataclass
class Replacement:
    """Suggested code replacement."""
    start: Position
    end: Position
    content: str


@dataclass
class Suggestion:
    """Suggested fix for a finding."""
    message: str
    replacements: List[Replacement] = None

    def __post_init__(self):
        if self.replacements is None:
            self.replacements = []


@dataclass
class Finding:
    """Normalized static analysis finding."""
    id: str
    rule_id: str
    rule_name: str
    message: str
    severity: str
    category: str
    location: Location
    source_tool: str
    suggestion: Optional[Suggestion] = None


@dataclass
class Metadata:
    """Metadata about the analysis run."""
    tool: str
    version: str
    total_findings: int
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class NormalizedFindings:
    """Container for normalized findings with metadata."""
    findings: List[Finding]
    metadata: Metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "findings": [asdict(finding) for finding in self.findings],
            "metadata": asdict(self.metadata)
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Union[str, Path]) -> None:
        """Save to JSON file."""
        Path(path).write_text(self.to_json())


class RuffNormalizer:
    """Normalizes Ruff JSON output to unified schema."""

    SEVERITY_MAP = {
        "E": Severity.ERROR.value,
        "W": Severity.WARNING.value,
        "F": Severity.ERROR.value,  # Flake8 errors
        "I": Severity.INFO.value,  # Import sorting
        "N": Severity.WARNING.value,  # Naming conventions
        "UP": Severity.WARNING.value,  # pyupgrade
        "B": Severity.WARNING.value,  # flake8-bugbear
        "A": Severity.WARNING.value,  # flake8-builtins
        "COM": Severity.WARNING.value,  # flake8-commas
        "C4": Severity.WARNING.value,  # flake8-comprehensions
        "DTZ": Severity.WARNING.value,  # flake8-datetimez
        "T10": Severity.WARNING.value,  # flake8-debugger
        "DJ": Severity.WARNING.value,  # flake8-django
        "EM": Severity.WARNING.value,  # flake8-errmsg
        "EXE": Severity.WARNING.value,  # flake8-executable
        "FA": Severity.WARNING.value,  # flake8-future-annotations
        "ISC": Severity.WARNING.value,  # flake8-implicit-str-concat
        "ICN": Severity.WARNING.value,  # flake8-import-conventions
        "G": Severity.WARNING.value,  # flake8-logging-format
        "INP": Severity.WARNING.value,  # flake8-no-pep420
        "PIE": Severity.WARNING.value,  # flake8-pie
        "T20": Severity.WARNING.value,  # flake8-print
        "PYI": Severity.WARNING.value,  # flake8-pyi
        "PT": Severity.WARNING.value,  # flake8-pytest-style
        "Q": Severity.WARNING.value,  # flake8-quotes
        "RSE": Severity.WARNING.value,  # flake8-raise
        "RET": Severity.WARNING.value,  # flake8-return
        "SLF": Severity.WARNING.value,  # flake8-self
        "SLOT": Severity.WARNING.value,  # flake8-slots
        "SIM": Severity.WARNING.value,  # flake8-simplify
        "TID": Severity.WARNING.value,  # flake8-tidy-imports
        "TCH": Severity.WARNING.value,  # flake8-type-checking
        "INT": Severity.WARNING.value,  # flake8-gettext
        "ARG": Severity.WARNING.value,  # flake8-unused-arguments
        "PTH": Severity.WARNING.value,  # flake8-use-pathlib
        "TD": Severity.INFO.value,  # flake8-todos
        "FIX": Severity.INFO.value,  # flake8-fixme
        "ERA": Severity.WARNING.value,  # eradicate
        "PD": Severity.WARNING.value,  # pandas-vet
        "PGH": Severity.WARNING.value,  # pygrep-hooks
        "PL": Severity.WARNING.value,  # Pylint
        "TRY": Severity.WARNING.value,  # tryceratops
        "FLY": Severity.WARNING.value,  # flynt
        "NPY": Severity.WARNING.value,  # NumPy-specific rules
        "AIR": Severity.WARNING.value,  # Airflow
        "PERF": Severity.WARNING.value,  # Perflint
        "FURB": Severity.WARNING.value,  # refurb
        "LOG": Severity.WARNING.value,  # flake8-logging
        "RUF": Severity.WARNING.value,  # Ruff-specific rules
    }

    CATEGORY_MAP = {
        "E": Category.STYLE.value,  # pycodestyle errors
        "W": Category.STYLE.value,  # pycodestyle warnings
        "F": Category.CORRECTNESS.value,  # Pyflakes
        "I": Category.IMPORT.value,  # isort
        "N": Category.STYLE.value,  # pep8-naming
        "UP": Category.STYLE.value,  # pyupgrade
        "B": Category.CORRECTNESS.value,  # flake8-bugbear
        "A": Category.CORRECTNESS.value,  # flake8-builtins
        "COM": Category.STYLE.value,  # flake8-commas
        "C4": Category.STYLE.value,  # flake8-comprehensions
        "DTZ": Category.CORRECTNESS.value,  # flake8-datetimez
        "T10": Category.CORRECTNESS.value,  # flake8-debugger
        "DJ": Category.CORRECTNESS.value,  # flake8-django
        "EM": Category.STYLE.value,  # flake8-errmsg
        "EXE": Category.CORRECTNESS.value,  # flake8-executable
        "FA": Category.TYPING.value,  # flake8-future-annotations
        "ISC": Category.STYLE.value,  # flake8-implicit-str-concat
        "ICN": Category.IMPORT.value,  # flake8-import-conventions
        "G": Category.STYLE.value,  # flake8-logging-format
        "INP": Category.IMPORT.value,  # flake8-no-pep420
        "PIE": Category.CORRECTNESS.value,  # flake8-pie
        "T20": Category.STYLE.value,  # flake8-print
        "PYI": Category.TYPING.value,  # flake8-pyi
        "PT": Category.STYLE.value,  # flake8-pytest-style
        "Q": Category.STYLE.value,  # flake8-quotes
        "RSE": Category.CORRECTNESS.value,  # flake8-raise
        "RET": Category.CORRECTNESS.value,  # flake8-return
        "SLF": Category.CORRECTNESS.value,  # flake8-self
        "SLOT": Category.PERFORMANCE.value,  # flake8-slots
        "SIM": Category.STYLE.value,  # flake8-simplify
        "TID": Category.IMPORT.value,  # flake8-tidy-imports
        "TCH": Category.TYPING.value,  # flake8-type-checking
        "INT": Category.CORRECTNESS.value,  # flake8-gettext
        "ARG": Category.CORRECTNESS.value,  # flake8-unused-arguments
        "PTH": Category.STYLE.value,  # flake8-use-pathlib
        "TD": Category.STYLE.value,  # flake8-todos
        "FIX": Category.STYLE.value,  # flake8-fixme
        "ERA": Category.STYLE.value,  # eradicate
        "PD": Category.CORRECTNESS.value,  # pandas-vet
        "PGH": Category.CORRECTNESS.value,  # pygrep-hooks
        "PL": Category.CORRECTNESS.value,  # Pylint
        "TRY": Category.CORRECTNESS.value,  # tryceratops
        "FLY": Category.STYLE.value,  # flynt
        "NPY": Category.CORRECTNESS.value,  # NumPy-specific rules
        "AIR": Category.CORRECTNESS.value,  # Airflow
        "PERF": Category.PERFORMANCE.value,  # Perflint
        "FURB": Category.STYLE.value,  # refurb
        "LOG": Category.CORRECTNESS.value,  # flake8-logging
        "RUF": Category.STYLE.value,  # Ruff-specific rules
    }

    def _normalize_file_path(self, file_path: str) -> str:
        """Normalize file path to be relative to git root.
        
        Args:
            file_path: Absolute or relative file path
            
        Returns:
            Path relative to git root
        """
        import subprocess
        import os
        
        # DEBUG: Log to file for async debugging
        with open("/tmp/patchpro_debug.log", "a") as f:
            f.write(f"[RuffNormalizer-{os.getpid()}] INPUT: {file_path}\n")
            f.write(f"[RuffNormalizer-{os.getpid()}] CWD: {os.getcwd()}\n")
        
        # If already relative, return as-is
        path_obj = Path(file_path)
        if not path_obj.is_absolute():
            with open("/tmp/patchpro_debug.log", "a") as f:
                f.write(f"[RuffNormalizer-{os.getpid()}] Already relative, returning: {file_path}\n")
            return file_path
        
        # Find git root
        try:
            # Try from the file's directory
            file_dir = path_obj.parent if path_obj.is_file() else path_obj
            with open("/tmp/patchpro_debug.log", "a") as f:
                f.write(f"[RuffNormalizer-{os.getpid()}] file_dir for git command: {file_dir}\n")
            
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=file_dir,
                capture_output=True,
                text=True,
                check=True
            )
            git_root_str = result.stdout.strip()
            git_root = Path(git_root_str)
            
            with open("/tmp/patchpro_debug.log", "a") as f:
                f.write(f"[RuffNormalizer-{os.getpid()}] git stdout: '{result.stdout}'\n")
                f.write(f"[RuffNormalizer-{os.getpid()}] git stdout stripped: '{git_root_str}'\n")
                f.write(f"[RuffNormalizer-{os.getpid()}] git root Path object: '{git_root}'\n")
            
            # Make relative to git root
            try:
                resolved_path = path_obj.resolve()
                with open("/tmp/patchpro_debug.log", "a") as f:
                    f.write(f"[RuffNormalizer-{os.getpid()}] RESOLVED PATH: {resolved_path}\n")
                    f.write(f"[RuffNormalizer-{os.getpid()}] GIT ROOT: {git_root}\n")
                    f.write(f"[RuffNormalizer-{os.getpid()}] IS RESOLVED UNDER GIT ROOT? {resolved_path.is_relative_to(git_root) if hasattr(resolved_path, 'is_relative_to') else 'N/A'}\n")
                
                rel_path = resolved_path.relative_to(git_root)
                with open("/tmp/patchpro_debug.log", "a") as f:
                    f.write(f"[RuffNormalizer-{os.getpid()}] OUTPUT: {rel_path}\n")
                return str(rel_path)
            except ValueError:
                # Path not under git root, strip leading slash
                result_path = str(path_obj).lstrip('/')
                with open("/tmp/patchpro_debug.log", "a") as f:
                    f.write(f"[RuffNormalizer-{os.getpid()}] Outside git root, returning: {result_path}\n")
                return result_path
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # Not in git repo or git not available, strip leading slash
            result_path = str(path_obj).lstrip('/')
            with open("/tmp/patchpro_debug.log", "a") as f:
                f.write(f"[RuffNormalizer-{os.getpid()}] Git error: {e}, returning: {result_path}\n")
            return result_path

    def normalize(self, ruff_output: Union[str, Dict, List]) -> NormalizedFindings:
        """Normalize Ruff JSON output."""
        if isinstance(ruff_output, str):
            data = json.loads(ruff_output)
        else:
            data = ruff_output

        # Ruff outputs a list of findings directly
        if not isinstance(data, list):
            raise ValueError("Expected Ruff output to be a list of findings")

        findings = []
        for item in data:
            finding = self._convert_ruff_finding(item)
            if finding:
                findings.append(finding)

        metadata = Metadata(
            tool="ruff",
            version="0.5.7",  # From pyproject.toml
            total_findings=len(findings)
        )

        return NormalizedFindings(findings=findings, metadata=metadata)

    def _convert_ruff_finding(self, ruff_finding: Dict) -> Optional[Finding]:
        """Convert a single Ruff finding to normalized format."""
        try:
            # Extract rule code and determine severity/category
            rule_code = ruff_finding["code"]
            rule_prefix = rule_code.split("-")[0] if "-" in rule_code else rule_code[:1]
            
            severity = self.SEVERITY_MAP.get(rule_prefix, Severity.WARNING.value)
            category = self.CATEGORY_MAP.get(rule_prefix, Category.CORRECTNESS.value)

            # Create location with normalized file path
            location = Location(
                file=self._normalize_file_path(ruff_finding["filename"]),
                line=ruff_finding["location"]["row"],
                column=ruff_finding["location"]["column"],
                end_line=ruff_finding["end_location"]["row"] if ruff_finding.get("end_location") else None,
                end_column=ruff_finding["end_location"]["column"] if ruff_finding.get("end_location") else None
            )

            # Generate unique ID
            finding_id = self._generate_id(rule_code, location)

            # Handle fix/suggestion if present
            suggestion = None
            if ruff_finding.get("fix"):
                suggestion = self._convert_ruff_fix(ruff_finding["fix"])

            return Finding(
                id=finding_id,
                rule_id=rule_code,
                rule_name=ruff_finding.get("message", "").split(":")[0] if ":" in ruff_finding.get("message", "") else rule_code,
                message=ruff_finding["message"],
                severity=severity,
                category=category,
                location=location,
                source_tool="ruff",
                suggestion=suggestion
            )

        except KeyError as e:
            print(f"Warning: Skipping malformed Ruff finding, missing key: {e}")
            return None

    def _convert_ruff_fix(self, fix_data: Dict) -> Optional[Suggestion]:
        """Convert Ruff fix data to suggestion format."""
        if not fix_data.get("edits"):
            return None

        replacements = []
        for edit in fix_data["edits"]:
            replacement = Replacement(
                start=Position(
                    line=edit["location"]["row"],
                    column=edit["location"]["column"]
                ),
                end=Position(
                    line=edit["end_location"]["row"],
                    column=edit["end_location"]["column"]
                ),
                content=edit["content"]
            )
            replacements.append(replacement)

        return Suggestion(
            message=fix_data.get("message", "Auto-fix available"),
            replacements=replacements
        )

    def _generate_id(self, rule_code: str, location: Location) -> str:
        """Generate unique ID for a finding."""
        content = f"{rule_code}:{location.file}:{location.line}:{location.column}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


class SemgrepNormalizer:
    """Normalizes Semgrep JSON output to unified schema."""

    SEVERITY_MAP = {
        "ERROR": Severity.ERROR.value,
        "WARNING": Severity.WARNING.value,
        "INFO": Severity.INFO.value,
        "HIGH": Severity.ERROR.value,
        "MEDIUM": Severity.WARNING.value,
        "LOW": Severity.INFO.value,
    }

    def _normalize_file_path(self, file_path: str) -> str:
        """Normalize file path to be relative to git root.
        
        Args:
            file_path: Absolute or relative file path
            
        Returns:
            Path relative to git root
        """
        import subprocess
        
        # If already relative, return as-is
        path_obj = Path(file_path)
        if not path_obj.is_absolute():
            return file_path
        
        # Find git root
        try:
            # Try from the file's directory
            file_dir = path_obj.parent if path_obj.is_file() else path_obj
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=file_dir,
                capture_output=True,
                text=True,
                check=True
            )
            git_root = Path(result.stdout.strip())
            
            # Make relative to git root
            try:
                rel_path = path_obj.resolve().relative_to(git_root)
                return str(rel_path)
            except ValueError:
                # Path not under git root, strip leading slash
                return str(path_obj).lstrip('/')
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Not in git repo or git not available, strip leading slash
            return str(path_obj).lstrip('/')

    def normalize(self, semgrep_output: Union[str, Dict]) -> NormalizedFindings:
        """Normalize Semgrep JSON output."""
        if isinstance(semgrep_output, str):
            data = json.loads(semgrep_output)
        else:
            data = semgrep_output

        if not isinstance(data, dict) or "results" not in data:
            raise ValueError("Expected Semgrep output to have 'results' key")

        findings = []
        for item in data["results"]:
            finding = self._convert_semgrep_finding(item)
            if finding:
                findings.append(finding)

        metadata = Metadata(
            tool="semgrep",
            version="1.84.0",  # From pyproject.toml
            total_findings=len(findings)
        )

        return NormalizedFindings(findings=findings, metadata=metadata)

    def _convert_semgrep_finding(self, semgrep_finding: Dict) -> Optional[Finding]:
        """Convert a single Semgrep finding to normalized format."""
        try:
            # Extract rule information
            check_id = semgrep_finding.get("check_id", "")
            rule_id = check_id.split(".")[-1] if "." in check_id else check_id

            # Map severity
            severity_raw = semgrep_finding.get("extra", {}).get("severity", "WARNING").upper()
            severity = self.SEVERITY_MAP.get(severity_raw, Severity.WARNING.value)

            # Determine category based on rule ID patterns
            category = self._determine_category(check_id)

            # Create location with normalized file path
            start_pos = semgrep_finding.get("start", {})
            end_pos = semgrep_finding.get("end", {})
            
            location = Location(
                file=self._normalize_file_path(semgrep_finding.get("path", "")),
                line=start_pos.get("line", 1),
                column=start_pos.get("col", 1),
                end_line=end_pos.get("line"),
                end_column=end_pos.get("col")
            )

            # Generate unique ID
            finding_id = self._generate_id(check_id, location)

            # Handle suggestions if present
            suggestion = None
            extra = semgrep_finding.get("extra", {})
            if extra.get("fix"):
                suggestion = Suggestion(message=f"Fix available: {extra.get('fix')}")

            return Finding(
                id=finding_id,
                rule_id=rule_id,
                rule_name=semgrep_finding.get("extra", {}).get("metadata", {}).get("shortDescription", rule_id),
                message=semgrep_finding.get("extra", {}).get("message", semgrep_finding.get("message", "")),
                severity=severity,
                category=category,
                location=location,
                source_tool="semgrep",
                suggestion=suggestion
            )

        except Exception as e:
            print(f"Warning: Skipping malformed Semgrep finding: {e}")
            return None

    def _determine_category(self, check_id: str) -> str:
        """Determine category based on Semgrep rule ID."""
        check_id_lower = check_id.lower()
        
        if "security" in check_id_lower or "crypto" in check_id_lower or "auth" in check_id_lower:
            return Category.SECURITY.value
        elif "performance" in check_id_lower or "perf" in check_id_lower:
            return Category.PERFORMANCE.value
        elif "style" in check_id_lower or "format" in check_id_lower:
            return Category.STYLE.value
        elif "import" in check_id_lower:
            return Category.IMPORT.value
        elif "type" in check_id_lower or "typing" in check_id_lower:
            return Category.TYPING.value
        elif "complexity" in check_id_lower or "complex" in check_id_lower:
            return Category.COMPLEXITY.value
        else:
            return Category.CORRECTNESS.value

    def _generate_id(self, check_id: str, location: Location) -> str:
        """Generate unique ID for a finding."""
        content = f"{check_id}:{location.file}:{location.line}:{location.column}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


class FindingsAnalyzer:
    """Main analyzer class for normalizing and processing findings."""

    def __init__(self):
        self.ruff_normalizer = RuffNormalizer()
        self.semgrep_normalizer = SemgrepNormalizer()

    def normalize_findings(self, tool_outputs: Dict[str, Union[str, Dict, List]]) -> List[NormalizedFindings]:
        """Normalize findings from multiple tools."""
        results = []

        for tool_name, output in tool_outputs.items():
            if tool_name.lower() == "ruff":
                normalized = self.ruff_normalizer.normalize(output)
                results.append(normalized)
            elif tool_name.lower() == "semgrep":
                normalized = self.semgrep_normalizer.normalize(output)
                results.append(normalized)
            else:
                print(f"Warning: Unknown tool '{tool_name}', skipping normalization")

        return results

    def merge_findings(self, normalized_results: List[NormalizedFindings]) -> NormalizedFindings:
        """Merge findings from multiple tools, removing duplicates."""
        all_findings = []
        tools_used = []
        total_findings = 0

        for result in normalized_results:
            all_findings.extend(result.findings)
            tools_used.append(result.metadata.tool)
            total_findings += result.metadata.total_findings

        # Remove duplicates based on location and rule similarity
        deduplicated = self._deduplicate_findings(all_findings)

        metadata = Metadata(
            tool=",".join(set(tools_used)),
            version="merged",
            total_findings=len(deduplicated)
        )

        return NormalizedFindings(findings=deduplicated, metadata=metadata)

    def _deduplicate_findings(self, findings: List[Finding]) -> List[Finding]:
        """Remove duplicate findings based on location and rule."""
        seen = set()
        deduplicated = []

        for finding in findings:
            # Create a key based on location and rule
            key = (
                finding.location.file,
                finding.location.line,
                finding.location.column,
                finding.rule_id
            )
            
            if key not in seen:
                seen.add(key)
                deduplicated.append(finding)

        return deduplicated

    def load_and_normalize(self, analysis_dir: Union[str, Path]) -> NormalizedFindings:
        """Load analysis results from directory and normalize them."""
        analysis_path = Path(analysis_dir)
        tool_outputs = {}

        # Look for known tool outputs
        for json_file in analysis_path.glob("*.json"):
            filename = json_file.stem.lower()
            
            try:
                content = json.loads(json_file.read_text())
                
                # Try to identify tool by filename or content structure
                if "ruff" in filename or (isinstance(content, list) and content and "code" in content[0]):
                    tool_outputs["ruff"] = content
                elif "semgrep" in filename or (isinstance(content, dict) and "results" in content):
                    tool_outputs["semgrep"] = content
                else:
                    print(f"Warning: Could not identify tool for {json_file}")
            
            except Exception as e:
                print(f"Warning: Failed to load {json_file}: {e}")

        # Normalize and merge
        normalized_results = self.normalize_findings(tool_outputs)
        
        if len(normalized_results) == 1:
            return normalized_results[0]
        elif len(normalized_results) > 1:
            return self.merge_findings(normalized_results)
        else:
            # Return empty results
            metadata = Metadata(tool="none", version="0.0.0", total_findings=0)
            return NormalizedFindings(findings=[], metadata=metadata)