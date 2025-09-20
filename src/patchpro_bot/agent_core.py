"""Core agent orchestrator for the patch bot pipeline."""

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .analysis import AnalysisReader, FindingAggregator
from .llm import LLMClient, PromptBuilder, ResponseParser, ResponseType
from .diff import DiffGenerator, FileReader, PatchWriter
from .models import AnalysisFinding


logger = logging.getLogger(__name__)


class PromptStrategy(Enum):
    """Different strategies for prompting the LLM."""
    AUTO = "auto"           # Automatically choose based on findings
    CODE_FIXES = "code_fixes"     # Always use code fixes
    DIFF_PATCHES = "diff_patches" # Always use diff patches
    SINGLE_DIFF = "single_diff"   # Use single file diff generation


@dataclass
class AgentConfig:
    """Configuration for the PatchPro agent."""
    # Directory settings
    analysis_dir: Path = Path("artifact/analysis")
    artifact_dir: Path = Path("artifact") 
    base_dir: Path = Path.cwd()
    
    # LLM settings
    openai_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.1
    
    # Processing settings
    max_findings: int = 20
    max_files_per_batch: int = 5
    
    # Output settings
    combine_patches: bool = True
    generate_summary: bool = True
    
    # New fields for structured responses
    response_format: ResponseType = ResponseType.CODE_FIXES
    prompt_strategy: PromptStrategy = PromptStrategy.AUTO
    max_findings_per_request: int = 10
    include_file_contents: bool = True
    max_file_size_kb: int = 100
class AgentCore:
    """Core orchestrator for the patch bot pipeline."""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize the agent core.
        
        Args:
            config: Agent configuration
        """
        self.config = config or AgentConfig()
        
        # Initialize components
        self.analysis_reader = AnalysisReader(self.config.analysis_dir)
        self.file_reader = FileReader(self.config.base_dir)
        self.diff_generator = DiffGenerator(self.file_reader)
        self.patch_writer = PatchWriter(self.config.artifact_dir)
        
        # Initialize LLM components
        self.llm_client = None
        self.prompt_builder = PromptBuilder()
        self.response_parser = ResponseParser()
        
        # Setup logging
        self._setup_logging()
    
    async def run(self) -> Dict[str, any]:
        """Run the complete patch bot pipeline.
        
        Returns:
            Dictionary with pipeline results and statistics
        """
        logger.info("Starting patch bot pipeline")
        
        try:
            # Step 1: Read analysis findings
            findings = self._load_analysis_findings()
            if not findings:
                return {"status": "no_findings", "message": "No analysis findings found"}
            
            # Step 2: Process findings
            aggregator = self._process_findings(findings)
            
            # Step 3: Generate suggestions using LLM
            llm_response = await self._generate_llm_suggestions(aggregator)
            if not llm_response:
                return {"status": "llm_failed", "message": "Failed to generate LLM suggestions"}
            
            # Step 4: Parse LLM response
            code_fixes, diff_patches = self._parse_llm_response(llm_response)
            
            # Step 5: Generate and write diffs
            patch_results = self._generate_and_write_patches(code_fixes, diff_patches)
            
            # Step 6: Generate report
            report_path = self._generate_report(aggregator, patch_results)
            
            # Compile results
            results = {
                "status": "success",
                "findings_count": len(findings),
                "fixes_generated": len(code_fixes) + len(diff_patches),
                "patches_written": len(patch_results.get("patch_paths", [])),
                "report_path": str(report_path) if report_path else None,
                "patch_paths": [str(p) for p in patch_results.get("patch_paths", [])],
                "combined_patch": str(patch_results.get("combined_patch")) if patch_results.get("combined_patch") else None,
            }
            
            logger.info(f"Pipeline completed successfully: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def _load_analysis_findings(self) -> List[AnalysisFinding]:
        """Load and validate analysis findings.
        
        Returns:
            List of analysis findings
        """
        logger.info("Loading analysis findings")
        
        if not self.config.analysis_dir.exists():
            logger.warning(f"Analysis directory does not exist: {self.config.analysis_dir}")
            return []
        
        findings = self.analysis_reader.read_all_findings()
        logger.info(f"Loaded {len(findings)} findings")
        
        return findings
    
    def _process_findings(self, findings: List[AnalysisFinding]) -> FindingAggregator:
        """Process and filter findings.
        
        Args:
            findings: Raw findings list
            
        Returns:
            Processed findings aggregator
        """
        logger.info("Processing findings")
        
        aggregator = FindingAggregator(findings)
        
        # Apply processing steps
        aggregator = (
            aggregator
            .deduplicate()
            .sort_by_priority()
            .limit_findings(self.config.max_findings)
        )
        
        summary = aggregator.get_summary()
        logger.info(f"Processed findings: {summary}")
        
        return aggregator
    
    async def _generate_llm_suggestions(self, aggregator: FindingAggregator) -> Optional[str]:
        """Generate suggestions using LLM.
        
        Args:
            aggregator: Processed findings
            
        Returns:
            LLM response content or None if failed
        """
        logger.info("Generating LLM suggestions")
        
        # Initialize LLM client if needed
        if self.llm_client is None:
            try:
                api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.error("OpenAI API key not provided")
                    return None
                
                self.llm_client = LLMClient(
                    api_key=api_key,
                    model=self.config.llm_model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                )
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")
                return None
        
        # Determine effective strategy and build appropriate prompt
        effective_strategy = self._get_effective_strategy(aggregator.findings)
        logger.info(f"Using prompt strategy: {effective_strategy.value}")
        
        if effective_strategy == PromptStrategy.CODE_FIXES:
            prompt = self.prompt_builder.build_code_fix_prompt(
                aggregator, 
                file_reader=self.file_reader
            )
            logger.info("Using code fixes prompt format")
        elif effective_strategy in [PromptStrategy.DIFF_PATCHES, PromptStrategy.SINGLE_DIFF]:
            # For diff patches, use batch approach
            file_fixes = self._group_findings_by_file(aggregator)
            file_contents = self._get_file_contents_for_findings(file_fixes)
            prompt = self.prompt_builder.build_batch_diff_prompt(file_fixes, file_contents)
            logger.info("Using diff patches prompt format")
        else:
            logger.error(f"Unknown prompt strategy: {effective_strategy}")
            return None
            
        system_prompt = self.prompt_builder._get_system_prompt()
        
        try:
            # Generate suggestions asynchronously
            response = await self.llm_client.generate_suggestions(
                prompt=prompt,
                system_prompt=system_prompt,
            )
            
            logger.info(f"Generated LLM response: {len(response.content)} characters")
            return response.content
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return None
    
    def _parse_llm_response(self, response_content: str) -> Tuple[List, List]:
        """Parse LLM response to extract fixes and patches.
        
        Args:
            response_content: Raw LLM response
            
        Returns:
            Tuple of (code_fixes, diff_patches)
        """
        logger.info("Parsing LLM response")
        
        # Parse response based on configured format
        parsed_response = self.response_parser.parse_response(
            response_content, 
            expected_type=self.config.response_format
        )
        
        logger.info(f"Parsed {len(parsed_response.code_fixes)} code fixes and {len(parsed_response.diff_patches)} diff patches")
        
        # Return in the expected format for backward compatibility
        return parsed_response.code_fixes, parsed_response.diff_patches
    
    def _generate_and_write_patches(self, code_fixes: List, diff_patches: List) -> Dict[str, any]:
        """Generate and write patch files.
        
        Args:
            code_fixes: List of CodeFix objects
            diff_patches: List of DiffPatch objects
            
        Returns:
            Dictionary with patch generation results
        """
        logger.info("Generating and writing patches")
        
        all_diffs = {}
        
        # Generate diffs from code fixes
        if code_fixes:
            code_fix_diffs = self.diff_generator.generate_multiple_diffs(code_fixes)
            all_diffs.update(code_fix_diffs)
        
        # Process diff patches
        for diff_patch in diff_patches:
            diff_content = self.diff_generator.generate_diff_from_patch(diff_patch)
            if diff_content:
                all_diffs[diff_patch.file_path] = diff_content
        
        if not all_diffs:
            logger.warning("No diffs generated")
            return {"patch_paths": [], "combined_patch": None}
        
        # Write patches
        patch_paths = []
        combined_patch = None
        
        try:
            if self.config.combine_patches and len(all_diffs) > 1:
                # Write combined patch
                combined_patch = self.patch_writer.write_combined_patch(all_diffs)
                patch_paths.append(combined_patch)
            else:
                # Write individual patches
                individual_patches = self.patch_writer.write_multiple_patches(all_diffs)
                patch_paths.extend(individual_patches)
            
            # Write summary if configured
            if self.config.generate_summary:
                summary_path = self.patch_writer.write_patch_summary(all_diffs, patch_paths)
                logger.info(f"Generated patch summary: {summary_path}")
            
        except Exception as e:
            logger.error(f"Error writing patches: {e}")
            return {"patch_paths": [], "combined_patch": None}
        
        logger.info(f"Successfully wrote {len(patch_paths)} patch files")
        
        return {
            "patch_paths": patch_paths,
            "combined_patch": combined_patch,
            "diffs": all_diffs,
        }
    
    def _generate_report(self, aggregator: FindingAggregator, patch_results: Dict) -> Optional[Path]:
        """Generate markdown report.
        
        Args:
            aggregator: Processed findings
            patch_results: Patch generation results
            
        Returns:
            Path to generated report, or None if failed
        """
        logger.info("Generating report")
        
        try:
            summary = aggregator.get_summary()
            
            report_content = f"""# PatchPro Bot Report

Generated on: {Path.cwd()}/{self.config.artifact_dir}

## Summary

- **Total findings**: {summary['total_findings']}
- **Tools used**: {', '.join(summary['by_tool'].keys())}
- **Affected files**: {summary['affected_files']}
- **Patches generated**: {len(patch_results.get('patch_paths', []))}

## Findings Breakdown

### By Severity
{self._format_dict_as_list(summary['by_severity'])}

### By Tool
{self._format_dict_as_list(summary['by_tool'])}

### By Category
{self._format_dict_as_list(summary['by_category'])}

## Generated Patches

"""
            
            for patch_path in patch_results.get('patch_paths', []):
                report_content += f"- `{patch_path.name}`\n"
            
            if patch_results.get('combined_patch'):
                report_content += f"\n### Combined Patch\n\n`{patch_results['combined_patch'].name}`\n"
            
            report_content += "\n## Affected Files\n\n"
            for file_path in sorted(summary['file_list']):
                report_content += f"- `{file_path}`\n"
            
            # Write report
            report_path = self.config.artifact_dir / "report.md"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Generated report: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None
    
    def _format_dict_as_list(self, d: Dict) -> str:
        """Format dictionary as markdown list.
        
        Args:
            d: Dictionary to format
            
        Returns:
            Formatted markdown string
        """
        if not d:
            return "- None\n"
        
        return '\n'.join(f"- **{k}**: {v}" for k, v in d.items()) + '\n'
    
    def _get_effective_strategy(self, findings: List[AnalysisFinding]) -> PromptStrategy:
        """Determine the effective prompt strategy to use and update response format accordingly.
        
        Args:
            findings: List of findings to analyze
            
        Returns:
            Effective strategy to use
        """
        if self.config.prompt_strategy != PromptStrategy.AUTO:
            strategy = self.config.prompt_strategy
        else:
            # Auto strategy logic based on workload size
            num_findings = len(findings)
            unique_files = len(set(f.location.file for f in findings))
            
            # If many findings across many files, use diff patches for efficiency
            if num_findings > 3 or unique_files > 3:
                logger.info(f"Using DIFF_PATCHES strategy: {num_findings} findings across {unique_files} files")
                strategy = PromptStrategy.DIFF_PATCHES
            else:
                # Default to code fixes for smaller, manageable sets
                logger.info(f"Using CODE_FIXES strategy: {num_findings} findings across {unique_files} files")
                strategy = PromptStrategy.CODE_FIXES
            
            # Update config to reflect the chosen strategy
            self.config.prompt_strategy = strategy
        
        # Ensure response format matches the strategy
        if strategy == PromptStrategy.CODE_FIXES:
            self.config.response_format = ResponseType.CODE_FIXES
        elif strategy in [PromptStrategy.DIFF_PATCHES, PromptStrategy.SINGLE_DIFF]:
            self.config.response_format = ResponseType.DIFF_PATCHES
            
        return strategy

    def _group_findings_by_file(self, aggregator: FindingAggregator) -> Dict[str, List[AnalysisFinding]]:
        """Group findings by file path.
        
        Args:
            aggregator: Processed findings aggregator
            
        Returns:
            Dictionary mapping file paths to their findings
        """
        file_fixes = {}
        for finding in aggregator.findings:
            file_path = finding.location.file
            if file_path not in file_fixes:
                file_fixes[file_path] = []
            file_fixes[file_path].append(finding)
        return file_fixes
    
    def _get_file_contents_for_findings(self, file_fixes: Dict[str, List[AnalysisFinding]]) -> Dict[str, str]:
        """Get file contents for files that have findings.
        
        Args:
            file_fixes: Dictionary mapping file paths to their findings
            
        Returns:
            Dictionary mapping file paths to their content
        """
        file_contents = {}
        for file_path in file_fixes.keys():
            try:
                content = self.file_reader.read_file(file_path)
                if content:
                    file_contents[file_path] = content
                else:
                    logger.warning(f"Could not read content for file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
        return file_contents
    
    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


async def main():
    """Main entry point for the agent."""
    # Load configuration from environment
    config = AgentConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        max_findings=int(os.getenv("MAX_FINDINGS", "20")),
    )
    
    # Create and run agent
    agent = AgentCore(config)
    results = await agent.run()
    
    # Print results
    print(f"Pipeline status: {results['status']}")
    if results['status'] == 'success':
        print(f"Generated {results['fixes_generated']} fixes for {results['findings_count']} findings")
        print(f"Wrote {results['patches_written']} patch files")
        if results['report_path']:
            print(f"Report: {results['report_path']}")
    else:
        print(f"Error: {results.get('message', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
