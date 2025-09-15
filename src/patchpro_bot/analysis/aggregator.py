"""Aggregator for combining and organizing analysis findings."""

import logging
from typing import List, Dict, Set
from collections import defaultdict

from ..models import AnalysisFinding, Severity


logger = logging.getLogger(__name__)


class FindingAggregator:
    """Aggregates and organizes analysis findings for LLM processing."""
    
    def __init__(self, findings: List[AnalysisFinding]):
        """Initialize with a list of findings.
        
        Args:
            findings: List of analysis findings
        """
        self.findings = findings
        
    def get_summary(self) -> Dict[str, any]:
        """Get a summary of findings.
        
        Returns:
            Dictionary with summary statistics
        """
        total_findings = len(self.findings)
        
        # Count by tool
        by_tool = defaultdict(int)
        for finding in self.findings:
            by_tool[finding.tool] += 1
            
        # Count by severity
        by_severity = defaultdict(int)
        for finding in self.findings:
            by_severity[finding.severity.value] += 1
            
        # Count by category
        by_category = defaultdict(int)
        for finding in self.findings:
            if finding.category:
                by_category[finding.category] += 1
                
        # Get unique files
        unique_files = set(finding.location.file for finding in self.findings)
        
        return {
            "total_findings": total_findings,
            "by_tool": dict(by_tool),
            "by_severity": dict(by_severity),
            "by_category": dict(by_category),
            "affected_files": len(unique_files),
            "file_list": sorted(unique_files),
        }
    
    def get_findings_by_file(self) -> Dict[str, List[AnalysisFinding]]:
        """Group findings by file.
        
        Returns:
            Dictionary mapping file paths to findings
        """
        by_file = defaultdict(list)
        for finding in self.findings:
            by_file[finding.location.file].append(finding)
            
        return dict(by_file)
    
    def get_findings_by_severity(self, severity: Severity) -> List[AnalysisFinding]:
        """Get findings of a specific severity.
        
        Args:
            severity: Severity level to filter by
            
        Returns:
            List of findings with the specified severity
        """
        return [f for f in self.findings if f.severity == severity]
    
    def get_high_priority_findings(self) -> List[AnalysisFinding]:
        """Get high-priority findings (errors and high severity).
        
        Returns:
            List of high-priority findings
        """
        high_priority_severities = {Severity.ERROR, Severity.HIGH}
        return [f for f in self.findings if f.severity in high_priority_severities]
    
    def get_findings_with_fixes(self) -> List[AnalysisFinding]:
        """Get findings that have suggested fixes.
        
        Returns:
            List of findings with suggested fixes
        """
        return [f for f in self.findings if f.suggested_fix]
    
    def deduplicate(self) -> "FindingAggregator":
        """Remove duplicate findings based on location and rule.
        
        Returns:
            New FindingAggregator with deduplicated findings
        """
        seen = set()
        unique_findings = []
        
        for finding in self.findings:
            # Create a key based on file, line, rule_id
            key = (finding.location.file, finding.location.line, finding.rule_id)
            
            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)
            else:
                logger.debug(f"Skipping duplicate finding: {finding}")
                
        logger.info(f"Deduplicated {len(self.findings)} -> {len(unique_findings)} findings")
        return FindingAggregator(unique_findings)
    
    def filter_by_files(self, file_patterns: List[str]) -> "FindingAggregator":
        """Filter findings by file patterns.
        
        Args:
            file_patterns: List of file patterns to include
            
        Returns:
            New FindingAggregator with filtered findings
        """
        import fnmatch
        
        filtered_findings = []
        
        for finding in self.findings:
            file_path = finding.location.file
            
            # Check if file matches any pattern
            for pattern in file_patterns:
                if fnmatch.fnmatch(file_path, pattern):
                    filtered_findings.append(finding)
                    break
                    
        logger.info(f"Filtered {len(self.findings)} -> {len(filtered_findings)} findings by file patterns")
        return FindingAggregator(filtered_findings)
    
    def sort_by_priority(self) -> "FindingAggregator":
        """Sort findings by priority (severity and location).
        
        Returns:
            New FindingAggregator with sorted findings
        """
        severity_priority = {
            Severity.ERROR: 0,
            Severity.HIGH: 1,
            Severity.WARNING: 2,
            Severity.MEDIUM: 3,
            Severity.INFO: 4,
            Severity.LOW: 5,
        }
        
        sorted_findings = sorted(
            self.findings,
            key=lambda f: (
                severity_priority.get(f.severity, 10),  # Severity first
                f.location.file,  # Then by file
                f.location.line,  # Then by line
            )
        )
        
        return FindingAggregator(sorted_findings)
    
    def limit_findings(self, max_findings: int) -> "FindingAggregator":
        """Limit the number of findings.
        
        Args:
            max_findings: Maximum number of findings to keep
            
        Returns:
            New FindingAggregator with limited findings
        """
        if len(self.findings) <= max_findings:
            return self
            
        # Take the first max_findings (assuming they're already sorted by priority)
        limited_findings = self.findings[:max_findings]
        
        logger.info(f"Limited findings from {len(self.findings)} to {len(limited_findings)}")
        return FindingAggregator(limited_findings)
    
    def to_prompt_context(self, include_code_snippets: bool = True) -> str:
        """Convert findings to a formatted string for LLM prompts.
        
        Args:
            include_code_snippets: Whether to include code snippets in output
            
        Returns:
            Formatted string representation of findings
        """
        if not self.findings:
            return "No analysis findings to process."
            
        summary = self.get_summary()
        
        context = f"""Analysis Summary:
- Total findings: {summary['total_findings']}
- Tools: {', '.join(f"{tool} ({count})" for tool, count in summary['by_tool'].items())}
- Severity breakdown: {', '.join(f"{sev} ({count})" for sev, count in summary['by_severity'].items())}
- Affected files: {summary['affected_files']}

Detailed Findings:
"""
        
        for i, finding in enumerate(self.findings, 1):
            context += f"\n{i}. {finding.tool.upper()} - {finding.rule_id}"
            context += f"\n   File: {finding.location.file}:{finding.location.line}"
            context += f"\n   Severity: {finding.severity.value}"
            context += f"\n   Message: {finding.message}"
            
            if finding.category:
                context += f"\n   Category: {finding.category}"
                
            if include_code_snippets and finding.code_snippet:
                context += f"\n   Code:\n   ```\n   {finding.code_snippet}\n   ```"
                
            if finding.suggested_fix:
                context += f"\n   Suggested fix: {finding.suggested_fix}"
                
            context += "\n"
            
        return context
