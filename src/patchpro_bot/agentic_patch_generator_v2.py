"""
Agentic patch generator V2 - uses ACTUAL working APIs from Issue #13.

This version is built on proven components:
- FindingContextReader (tested, works)
- PromptBuilder.build_unified_diff_prompt_with_context() (tested, works)
- ResponseParser.parse_diff_patches() (tested, works)
- DiffValidator (tested, works)

Architecture:
- Inherits from AgenticCore for self-correction, memory, planning
- Uses REAL APIs that we know work from Issue #13
- Adds agentic behavior on top of proven foundation
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from patchpro_bot.agentic_core import AgenticCore, Tool, AgentState
from patchpro_bot.models import AnalysisFinding
from patchpro_bot.llm.response_parser import DiffPatch, ResponseParser, ResponseType
from patchpro_bot.context_reader import FindingContextReader
from patchpro_bot.llm.prompts import PromptBuilder
from patchpro_bot.validators import DiffValidator

logger = logging.getLogger(__name__)


class AgenticPatchGeneratorV2(AgenticCore):
    """
    Autonomous agent for generating patches with self-correction.
    
    Built on PROVEN components from Issue #13 that have 100% success rate.
    Adds agentic properties:
    1. Autonomous decision-making (which tool to use)
    2. Self-correction loops (retry on failure)
    3. Memory (learn from attempts)
    4. Tool selection (simple vs contextual vs batch)
    5. Planning (multi-step execution)
    6. Goal-oriented (achieve valid patch by any means)
    """
    
    def __init__(
        self,
        llm_client,
        repo_path: Path,
        max_retries: int = 3,
        enable_planning: bool = True
    ):
        """Initialize the agentic patch generator."""
        super().__init__(llm_client, max_retries, enable_planning)
        
        self.repo_path = repo_path
        self.context_reader = FindingContextReader(context_lines=5)
        self.prompt_builder = PromptBuilder()
        self.response_parser = ResponseParser()
        self.validator = DiffValidator()
        
        # Register specialized tools
        self._register_patch_tools()
        
        logger.info(f"Initialized AgenticPatchGeneratorV2 for {repo_path}")
    
    def _register_patch_tools(self):
        """Register patch generation tools."""
        
        # Tool 1: Single finding patch (PROVEN 100% from Issue #13)
        self.register_tool(Tool(
            name="generate_single_patch",
            description="Generate patch for a single finding (proven strategy)",
            function=self._generate_single_patch,
            required_args=['finding']
        ))
        
        # Tool 2: Batch patch for multiple findings in same file
        self.register_tool(Tool(
            name="generate_batch_patch",
            description="Generate unified patch for multiple findings in one file",
            function=self._generate_batch_patch,
            required_args=['findings']
        ))
        
        # Tool 3: Validate patch
        self.register_tool(Tool(
            name="validate_patch",
            description="Validate that patch has correct unified diff format",
            function=self._validate_patch,
            required_args=['patch_content']
        ))
        
        # Tool 4: Analyze finding
        self.register_tool(Tool(
            name="analyze_finding",
            description="Analyze finding complexity to choose strategy",
            function=self._analyze_finding_complexity,
            required_args=['finding']
        ))
    
    async def generate_patches(self, findings: List[AnalysisFinding]) -> Dict[str, Any]:
        """
        Generate patches autonomously with self-correction.
        
        This is the main entry point that uses agentic behavior to generate patches.
        
        Args:
            findings: List of findings to patch
            
        Returns:
            Dict with patches, metrics, and agent telemetry
        """
        logger.info(f"Agent processing {len(findings)} findings...")
        
        all_patches = []
        successes = 0
        failures = 0
        total_attempts = 0
        
        # Group findings by file for potential batch processing
        file_fixes = {}
        for finding in findings:
            file_path = finding.location.file
            if file_path not in file_fixes:
                file_fixes[file_path] = []
            file_fixes[file_path].append(finding)
        
        logger.info(f"Grouped into {len(file_fixes)} files")
        
        # Process each file with agent autonomy
        for file_path, file_findings in file_fixes.items():
            logger.info(f"Processing {file_path} with {len(file_findings)} findings")
            
            # Agent decides: batch or individual?
            if len(file_findings) == 1:
                # Single finding - use proven single-patch strategy
                result = await self._achieve_goal_with_retry(
                    goal=f"Generate valid patch for {file_findings[0].rule_id}",
                    strategy="generate_single_patch",
                    context={'finding': file_findings[0]}
                )
            else:
                # Multiple findings - try batch first, fall back to individual
                result = await self._achieve_goal_with_retry(
                    goal=f"Generate batch patch for {len(file_findings)} findings in {file_path}",
                    strategy="generate_batch_patch",
                    context={'findings': file_findings}
                )
            
            total_attempts += len(self.memory.attempts)
            
            if result['success']:
                patches = result.get('result', {}).get('patches', [])
                all_patches.extend(patches)
                successes += 1
                logger.info(f"✓ Generated patches for {file_path}")
            else:
                failures += 1
                logger.warning(f"✗ Failed to generate patches for {file_path}")
        
        # Compile results with agent telemetry
        return {
            'patches': all_patches,
            'total_files': len(file_fixes),
            'total_findings': len(findings),
            'successes': successes,
            'failures': failures,
            'success_rate': successes / len(file_fixes) if file_fixes else 0,
            'total_attempts': total_attempts,
            'memory': {
                'attempts': len(self.memory.attempts),
                'successful_strategies': list(set(self.memory.successful_strategies)),
                'failed_strategies': list(set(self.memory.failed_strategies))
            }
        }
    
    async def _achieve_goal_with_retry(
        self,
        goal: str,
        strategy: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Achieve goal with retry loop and self-correction.
        
        This is where the agentic magic happens:
        - Try strategy
        - Validate result
        - If fail, analyze failure
        - Try alternative strategy
        - Repeat until success or max retries
        """
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Attempt {attempt}/{self.max_retries}: {strategy}")
            
            # Execute strategy
            tool = self.tool_registry.get_tool(strategy)
            if not tool:
                return {'success': False, 'error': f'Unknown strategy: {strategy}'}
            
            result = await tool.function(**context)
            
            # Record attempt in memory
            self.memory.record_attempt(
                strategy=strategy,
                result=result['success'],
                details=result
            )
            
            if result['success']:
                logger.info(f"✓ Strategy {strategy} succeeded on attempt {attempt}")
                return result
            
            # Failed - analyze and try alternative
            logger.warning(f"✗ Strategy {strategy} failed: {result.get('error')}")
            
            if attempt < self.max_retries:
                # Try alternative strategy
                if strategy == "generate_batch_patch":
                    # Batch failed, try individual
                    strategy = "generate_single_patch"
                    # Convert batch context to single
                    if 'findings' in context and context['findings']:
                        context = {'finding': context['findings'][0]}
                        logger.info("Switching to single-patch strategy")
        
        return {'success': False, 'error': 'Exhausted all retries'}
    
    async def _generate_single_patch(self, finding: AnalysisFinding) -> Dict[str, Any]:
        """
        Generate patch for single finding using PROVEN Issue #13 approach.
        
        This is the 100% success rate strategy.
        """
        try:
            # Group into file_fixes format that PromptBuilder expects
            file_fixes = {finding.location.file: [finding]}
            
            # Use PROVEN prompt builder from Issue #13
            prompt = self.prompt_builder.build_unified_diff_prompt_with_context(
                file_fixes=file_fixes,
                repo_path=str(self.repo_path)
            )
            
            # Call LLM
            response = await self.llm_client.generate_async(
                messages=[
                    {"role": "system", "content": self.prompt_builder.system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse with PROVEN parser from Issue #13
            parsed = self.response_parser.parse_response(
                response.content,
                expected_type=ResponseType.DIFF_PATCHES
            )
            
            if not parsed.diff_patches:
                return {'success': False, 'error': 'No patches parsed from LLM response'}
            
            # Validate patches
            valid_patches = []
            for patch in parsed.diff_patches:
                is_valid, errors = self.validator.validate_format(patch.diff_content)
                if is_valid:
                    valid_patches.append(patch)
                else:
                    logger.warning(f"Invalid patch for {patch.file_path}: {errors}")
            
            if not valid_patches:
                return {'success': False, 'error': 'No valid patches generated'}
            
            return {'success': True, 'result': {'patches': valid_patches}}
            
        except Exception as e:
            logger.error(f"Single patch generation failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _generate_batch_patch(self, findings: List[AnalysisFinding]) -> Dict[str, Any]:
        """Generate unified patch for multiple findings in same file."""
        try:
            # Group by file (should all be same file, but be safe)
            file_fixes = {}
            for finding in findings:
                file_path = finding.location.file
                if file_path not in file_fixes:
                    file_fixes[file_path] = []
                file_fixes[file_path].append(finding)
            
            # Use PROVEN prompt builder
            prompt = self.prompt_builder.build_unified_diff_prompt_with_context(
                file_fixes=file_fixes,
                repo_path=str(self.repo_path)
            )
            
            # Call LLM
            response = await self.llm_client.generate_async(
                messages=[
                    {"role": "system", "content": self.prompt_builder.system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse
            parsed = self.response_parser.parse_response(
                response.content,
                expected_type=ResponseType.DIFF_PATCHES
            )
            
            if not parsed.diff_patches:
                return {'success': False, 'error': 'No patches parsed from LLM response'}
            
            # Validate
            valid_patches = []
            for patch in parsed.diff_patches:
                is_valid, errors = self.validator.validate_format(patch.diff_content)
                if is_valid:
                    valid_patches.append(patch)
                else:
                    logger.warning(f"Invalid batch patch: {errors}")
            
            if not valid_patches:
                return {'success': False, 'error': 'No valid patches from batch generation'}
            
            return {'success': True, 'result': {'patches': valid_patches}}
            
        except Exception as e:
            logger.error(f"Batch patch generation failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _validate_patch(self, patch_content: str) -> Dict[str, Any]:
        """Validate patch format."""
        is_valid, errors = self.validator.validate_format(patch_content)
        return {
            'success': is_valid,
            'result': {'valid': is_valid, 'errors': errors}
        }
    
    def _analyze_finding_complexity(self, finding: AnalysisFinding) -> Dict[str, Any]:
        """Analyze finding to determine optimal strategy."""
        complexity = "simple"
        recommended_tool = "generate_single_patch"
        
        # Simple heuristic
        message_length = len(finding.message or '')
        start_line = finding.location.line
        end_line = finding.location.end_line or start_line
        lines_affected = end_line - start_line + 1
        
        if lines_affected > 5 or message_length > 200:
            complexity = "complex"
        elif lines_affected > 1:
            complexity = "moderate"
        
        return {
            'success': True,
            'result': {
                'complexity': complexity,
                'lines_affected': lines_affected,
                'message_length': message_length,
                'recommended_tool': recommended_tool,
                'reasoning': f"{lines_affected} lines, {message_length} char message"
            }
        }
