"""Reader for analysis JSON files."""

import json
import logging
from pathlib import Path
from typing import List, Any, Optional

from ..models import AnalysisFinding, RuffFinding, SemgrepFinding
from ..models.ruff import RuffRawFinding
from ..models.semgrep import SemgrepRawFinding


logger = logging.getLogger(__name__)


class AnalysisReader:
    """Reads and parses analysis JSON files from various tools."""
    
    def __init__(self, analysis_dir: Path = Path("artifact/analysis")):
        """Initialize the reader with analysis directory.
        
        Args:
            analysis_dir: Directory containing analysis JSON files
        """
        self.analysis_dir = analysis_dir
        
    def read_all_findings(self) -> List[AnalysisFinding]:
        """Read and parse all analysis findings from the directory.
        
        Returns:
            List of unified analysis findings
        """
        findings = []
        
        if not self.analysis_dir.exists():
            logger.warning(f"Analysis directory {self.analysis_dir} does not exist")
            return findings
        
        # Read all JSON files in the analysis directory
        for json_file in self.analysis_dir.glob("*.json"):
            try:
                file_findings = self._read_file(json_file)
                findings.extend(file_findings)
                logger.info(f"Loaded {len(file_findings)} findings from {json_file.name}")
            except Exception as e:
                logger.error(f"Failed to read {json_file}: {e}")
                continue
                
        logger.info(f"Total findings loaded: {len(findings)}")
        return findings
    
    def read_ruff_findings(self) -> List[RuffFinding]:
        """Read Ruff-specific findings.
        
        Returns:
            List of Ruff findings
        """
        findings = []
        
        for pattern in ["ruff*.json", "*ruff*.json"]:
            for json_file in self.analysis_dir.glob(pattern):
                try:
                    raw_data = self._load_json(json_file)
                    file_findings = self._parse_ruff_data(raw_data)
                    findings.extend(file_findings)
                    logger.info(f"Loaded {len(file_findings)} Ruff findings from {json_file.name}")
                except Exception as e:
                    logger.error(f"Failed to read Ruff file {json_file}: {e}")
                    
        return findings
    
    def read_semgrep_findings(self) -> List[SemgrepFinding]:
        """Read Semgrep-specific findings.
        
        Returns:
            List of Semgrep findings
        """
        findings = []
        
        for pattern in ["semgrep*.json", "*semgrep*.json"]:
            for json_file in self.analysis_dir.glob(pattern):
                try:
                    raw_data = self._load_json(json_file)
                    file_findings = self._parse_semgrep_data(raw_data)
                    findings.extend(file_findings)
                    logger.info(f"Loaded {len(file_findings)} Semgrep findings from {json_file.name}")
                except Exception as e:
                    logger.error(f"Failed to read Semgrep file {json_file}: {e}")
                    
        return findings
    
    def _read_file(self, json_file: Path) -> List[AnalysisFinding]:
        """Read and parse a single JSON file.
        
        Args:
            json_file: Path to JSON file
            
        Returns:
            List of analysis findings
        """
        raw_data = self._load_json(json_file)
        
        # Determine tool type based on filename or content structure
        tool_type = self._detect_tool_type(json_file, raw_data)
        
        if tool_type == "ruff":
            ruff_findings = self._parse_ruff_data(raw_data)
            return [finding for finding in ruff_findings]
        elif tool_type == "semgrep":
            semgrep_findings = self._parse_semgrep_data(raw_data)
            return [finding for finding in semgrep_findings]
        else:
            logger.warning(f"Unknown tool type for {json_file.name}")
            return []
    
    def _load_json(self, json_file: Path) -> Any:
        """Load JSON data from file.
        
        Args:
            json_file: Path to JSON file
            
        Returns:
            Parsed JSON data
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_file}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to read {json_file}: {e}")
            raise
    
    def _detect_tool_type(self, json_file: Path, data: Any) -> Optional[str]:
        """Detect the analysis tool type based on filename and content.
        
        Args:
            json_file: Path to JSON file
            data: Parsed JSON data
            
        Returns:
            Tool type ('ruff', 'semgrep') or None if unknown
        """
        filename = json_file.name.lower()
        
        # Check filename patterns
        if "ruff" in filename:
            return "ruff"
        elif "semgrep" in filename:
            return "semgrep"
        
        # Check content structure
        if isinstance(data, list) and data:
            first_item = data[0]
            if isinstance(first_item, dict):
                # Ruff findings have 'code', 'message', 'filename' fields
                if all(key in first_item for key in ['code', 'message', 'filename']):
                    return "ruff"
                # Semgrep findings have 'check_id', 'path', 'start', 'end' fields
                elif all(key in first_item for key in ['check_id', 'path', 'start', 'end']):
                    return "semgrep"
        
        return None
    
    def _parse_ruff_data(self, data: Any) -> List[RuffFinding]:
        """Parse Ruff JSON data.
        
        Args:
            data: Raw JSON data
            
        Returns:
            List of RuffFinding objects
        """
        findings = []
        
        if not isinstance(data, list):
            logger.warning("Ruff data is not a list")
            return findings
        
        for item in data:
            try:
                raw_finding = RuffRawFinding.model_validate(item)
                finding = RuffFinding.from_raw(raw_finding)
                findings.append(finding)
            except Exception as e:
                logger.error(f"Failed to parse Ruff finding: {e}")
                continue
                
        return findings
    
    def _parse_semgrep_data(self, data: Any) -> List[SemgrepFinding]:
        """Parse Semgrep JSON data.
        
        Args:
            data: Raw JSON data
            
        Returns:
            List of SemgrepFinding objects
        """
        findings = []
        
        # Semgrep output can be a dict with 'results' key or a list
        if isinstance(data, dict) and 'results' in data:
            results = data['results']
        elif isinstance(data, list):
            results = data
        else:
            logger.warning("Semgrep data format not recognized")
            return findings
        
        for item in results:
            try:
                raw_finding = SemgrepRawFinding.model_validate(item)
                finding = SemgrepFinding.from_raw(raw_finding)
                findings.append(finding)
            except Exception as e:
                logger.error(f"Failed to parse Semgrep finding: {e}")
                continue
                
        return findings
