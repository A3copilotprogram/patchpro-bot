"""Core agent orchestrator for the patch bot pipeline."""

import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .analysis import AnalysisReader, FindingAggregator
from .llm import LLMClient, PromptBuilder, ResponseParser
from .diff import DiffGenerator, FileReader, PatchWriter
from .models import AnalysisFinding


logger = logging.getLogger(__name__)


@dataclass 
class AgentConfig:
    """Configuration for the agent core."""
    # Directories
    analysis_dir: Path = Path("artifact/analysis")
    artifact_dir: Path = Path("artifact")
    base_dir: Path = Path.cwd()
    
    # LLM settings
    openai_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.1
    
    # Processing limits
    max_findings: int = 20
    max_files_per_batch: int = 5
    
    # Output settings
    combine_patches: bool = True
    generate_summary: bool = True


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
    
    def run(self) -> Dict[str, any]:
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
            llm_response = self._generate_llm_suggestions(aggregator)
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
    
    def _generate_llm_suggestions(self, aggregator: FindingAggregator) -> Optional[str]:
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
        
        # Build prompt
        prompt = self.prompt_builder.build_code_fix_prompt(
            aggregator, 
            file_reader=self.file_reader
        )
        system_prompt = self.prompt_builder._get_system_prompt()
        
        try:
            # Generate suggestions
            response = self.llm_client.generate_suggestions_sync(
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
        
        # Clean response content
        cleaned_content = self.response_parser.clean_response_content(response_content)
        
        # Parse code fixes
        code_fixes = self.response_parser.parse_code_fixes(cleaned_content)
        
        # Parse diff patches
        diff_patches = self.response_parser.parse_diff_patches(cleaned_content)
        
        logger.info(f"Parsed {len(code_fixes)} code fixes and {len(diff_patches)} diff patches")
        
        return code_fixes, diff_patches
    
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
    
    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


def main():
    """Main entry point for the agent."""
    # Load configuration from environment
    config = AgentConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        max_findings=int(os.getenv("MAX_FINDINGS", "20")),
    )
    
    # Create and run agent
    agent = AgentCore(config)
    results = agent.run()
    
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
    main()
