"""
Agentic patch generator - uses AgenticCore for autonomous patch generation.

This transforms the static pipeline into an autonomous agent that:
- Decides its own strategy for each finding
- Self-corrects when patches fail validation
- Learns from failures and adjusts approach
- Uses tools dynamically based on context
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from patchpro_bot.agentic_core import AgenticCore, Tool, AgentState
from patchpro_bot.models import AnalysisFinding
from patchpro_bot.llm.response_parser import DiffPatch, ResponseParser
from patchpro_bot.context_reader import FindingContextReader
from patchpro_bot.llm.prompts import PromptBuilder
from patchpro_bot.validators import DiffValidator

logger = logging.getLogger(__name__)


class AgenticPatchGenerator(AgenticCore):
    """
    Autonomous agent for generating patches with self-correction.
    
    This agent can:
    1. Analyze findings and decide optimal strategy
    2. Generate patches with context-aware prompts
    3. Validate patches and self-correct failures
    4. Learn from mistakes and improve
    5. Use different tools based on finding complexity
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
        self.context_reader = FindingContextReader()
        self.prompt_builder = PromptBuilder()
        self.response_parser = ResponseParser()
        self.validator = DiffValidator()
        
        # Register specialized tools
        self._register_patch_tools()
        
        logger.info(f"Initialized AgenticPatchGenerator for {repo_path}")
    
    def _register_patch_tools(self):
        """Register patch generation tools."""
        
        # Tool 1: Simple single-finding patch
        self.register_tool(Tool(
            name="generate_simple_patch",
            description="Generate patch for a single finding with basic context",
            function=self._generate_simple_patch,
            required_args=['finding']
        ))
        
        # Tool 2: Context-rich patch
        self.register_tool(Tool(
            name="generate_contextual_patch",
            description="Generate patch with extended file context",
            function=self._generate_contextual_patch,
            required_args=['finding', 'context_lines']
        ))
        
        # Tool 3: Multi-finding batch patch
        self.register_tool(Tool(
            name="generate_batch_patch",
            description="Generate unified patch for multiple findings in same file",
            function=self._generate_batch_patch,
            required_args=['findings']
        ))
        
        # Tool 4: Validate and fix patch
        self.register_tool(Tool(
            name="validate_and_fix_patch",
            description="Validate patch and attempt automatic fixes",
            function=self._validate_and_fix_patch,
            required_args=['patch_content']
        ))
        
        # Tool 5: Analyze finding complexity
        self.register_tool(Tool(
            name="analyze_finding",
            description="Analyze finding complexity to choose optimal strategy",
            function=self._analyze_finding_complexity,
            required_args=['finding']
        ))
    
    async def generate_patches(self, findings: List[AnalysisFinding]) -> Dict[str, Any]:
        """
        Generate patches autonomously with self-correction.
        
        Args:
            findings: List of findings to patch
            
        Returns:
            Dict with patches and success metrics
        """
        logger.info(f"Agent processing {len(findings)} findings...")
        
        patches = []
        successes = 0
        failures = 0
        
        for finding in findings:
            # Agent decides strategy and executes with retry
            result = await self.achieve_goal(
                goal=f"Generate valid patch for {finding.rule_id} in {finding.location.file}",
                context={
                    'finding': finding,
                    'repo_path': str(self.repo_path)
                }
            )
            
            if result['success']:
                patches.append(result['result']['patch'])
                successes += 1
                logger.info(f"✓ Generated patch for {finding.rule_id}")
            else:
                failures += 1
                logger.warning(f"✗ Failed to generate patch for {finding.rule_id}")
        
        return {
            'patches': patches,
            'total': len(findings),
            'successes': successes,
            'failures': failures,
            'success_rate': successes / len(findings) if findings else 0,
            'agent_state': self.get_state()
        }
    
    async def _execute_action(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute patch generation action.
        
        This is where agent autonomy happens:
        1. Analyze finding complexity
        2. Choose appropriate strategy/tool
        3. Generate patch with selected approach
        4. Return result for validation
        """
        finding = context['finding']
        attempt_number = context.get('attempt_number', 1)
        memory_context = context.get('memory_context', '')
        
        logger.info(f"Executing patch generation (attempt {attempt_number})...")
        
        # Step 1: Analyze finding to choose strategy
        analysis = self._analyze_finding_complexity(finding)
        complexity = analysis['result']['complexity']
        recommended_tool = analysis['result']['recommended_tool']
        
        logger.info(f"Finding complexity: {complexity}, using tool: {recommended_tool}")
        
        # Step 2: Adjust strategy based on past failures
        if attempt_number > 1 and 'failed' in memory_context.lower():
            # Agent learns: if previous attempts failed, use simpler strategy
            logger.info("Previous attempts failed - switching to simpler strategy")
            recommended_tool = "generate_simple_patch"
        
        # Step 3: Generate patch using chosen tool
        if recommended_tool == "generate_simple_patch":
            patch_result = await self._generate_simple_patch(finding)
        elif recommended_tool == "generate_contextual_patch":
            context_lines = 10 if attempt_number == 1 else 15  # More context on retry
            patch_result = await self._generate_contextual_patch(finding, context_lines)
        else:
            patch_result = await self._generate_simple_patch(finding)  # Fallback
        
        if not patch_result['success']:
            return patch_result
        
        patch = patch_result['result']
        
        return {
            'success': True,
            'patch': patch,
            'strategy': recommended_tool,
            'complexity': complexity,
            'attempt': attempt_number
        }
    
    async def _validate_result(self, result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, bool]:
        """
        Validate generated patch.
        
        Returns validation result with detailed error info for learning.
        """
        if not result.get('success'):
            return {'valid': False, 'error': 'Generation failed'}
        
        patch = result.get('patch')
        if not patch:
            return {'valid': False, 'error': 'No patch generated'}
        
        # Validate patch format
        format_valid = self.validator.validate_format(patch.content)
        if not format_valid:
            return {
                'valid': False,
                'error': 'Invalid patch format',
                'details': 'Patch does not follow unified diff format'
            }
        
        # Validate with git apply
        can_apply, error_msg = self.validator.can_apply(patch.content)
        if not can_apply:
            return {
                'valid': False,
                'error': f'git apply failed: {error_msg}',
                'details': error_msg
            }
        
        logger.info("✓ Patch validated successfully")
        return {'valid': True}
    
    def _analyze_finding_complexity(self, finding: AnalysisFinding) -> Dict[str, Any]:
        """
        Analyze finding to determine complexity and optimal strategy.
        
        Returns:
            Dict with complexity level and recommended tool
        """
        # Simple heuristic-based analysis
        complexity = "simple"
        recommended_tool = "generate_simple_patch"
        
        # Check message length
        message_length = len(finding.message or '')
        
        # Check if multi-line change needed
        start_line = finding.location.line
        end_line = finding.location.end_line or finding.location.line
        lines_affected = end_line - start_line + 1
        
        if lines_affected > 5 or message_length > 200:
            complexity = "complex"
            recommended_tool = "generate_contextual_patch"
        elif lines_affected > 1:
            complexity = "moderate"
            recommended_tool = "generate_contextual_patch"
        
        logger.debug(f"Analysis: {complexity} ({lines_affected} lines, {message_length} chars)")
        
        return {
            'success': True,
            'result': {
                'complexity': complexity,
                'lines_affected': lines_affected,
                'message_length': message_length,
                'recommended_tool': recommended_tool,
                'reasoning': f"{lines_affected} lines affected, {message_length} char message"
            }
        }
    
    async def _generate_simple_patch(self, finding: AnalysisFinding) -> Dict[str, Any]:
        """Generate patch with basic context (proven 100% success strategy)."""
        try:
            # Get minimal context
            context = self.context_reader.get_code_context(finding, context_lines=5)
            
            # Build prompt
            prompt = self.prompt_builder.build_user_prompt([finding], {finding.location.file: context})
            system_prompt = self.prompt_builder.build_system_prompt()
            
            # Call LLM
            response = await self.llm_client.generate_suggestions(
                prompt=prompt,
                system_prompt=system_prompt
            )
            
            # Parse response
            patches = self.response_parser.parse_diff_patches(response.content)
            
            if not patches:
                return {'success': False, 'error': 'No patches parsed from response'}
            
            # Return first patch
            patch = patches[0]
            
            # Normalize paths before returning
            patch.content = self.validator.normalize_diff_paths(patch.content)
            
            return {'success': True, 'result': patch}
            
        except Exception as e:
            logger.error(f"Simple patch generation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _generate_contextual_patch(self, finding: AnalysisFinding, context_lines: int) -> Dict[str, Any]:
        """Generate patch with extended context."""
        try:
            # Get extended context
            context = self.context_reader.get_code_context(finding, context_lines=context_lines)
            
            # Build prompt with emphasis on context
            prompt = self.prompt_builder.build_user_prompt([finding], {finding.location.file: context})
            system_prompt = self.prompt_builder.build_system_prompt()
            
            # Call LLM
            response = await self.llm_client.generate_suggestions(
                prompt=prompt,
                system_prompt=system_prompt
            )
            
            # Parse response
            patches = self.response_parser.parse_diff_patches(response.content)
            
            if not patches:
                return {'success': False, 'error': 'No patches parsed from response'}
            
            patch = patches[0]
            
            # Normalize paths
            patch.content = self.validator.normalize_diff_paths(patch.content)
            
            return {'success': True, 'result': patch}
            
        except Exception as e:
            logger.error(f"Contextual patch generation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _generate_batch_patch(self, findings: List[AnalysisFinding]) -> Dict[str, Any]:
        """Generate unified patch for multiple findings (experimental)."""
        # This is the multi-finding approach that currently has issues
        # Keeping it as a tool the agent can choose, but it will learn to avoid it
        try:
            # Group by file
            findings_by_file = {}
            for finding in findings:
                path = finding.location.file
                if path not in findings_by_file:
                    findings_by_file[path] = []
                findings_by_file[path].append(finding)
            
            # Get contexts
            contexts = {}
            for path, file_findings in findings_by_file.items():
                # Use first finding to get context
                contexts[path] = self.context_reader.get_full_file_content(file_findings[0])
            
            # Build prompt
            prompt = self.prompt_builder.build_user_prompt(findings, contexts)
            system_prompt = self.prompt_builder.build_system_prompt()
            
            # Call LLM
            response = await self.llm_client.generate_suggestions(
                prompt=prompt,
                system_prompt=system_prompt
            )
            
            # Parse response
            patches = self.response_parser.parse_diff_patches(response.content)
            
            if not patches:
                return {'success': False, 'error': 'No patches parsed from batch response'}
            
            patch = patches[0]
            patch.content = self.validator.normalize_diff_paths(patch.content)
            
            return {'success': True, 'result': patch}
            
        except Exception as e:
            logger.error(f"Batch patch generation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _validate_and_fix_patch(self, patch_content: str) -> Dict[str, Any]:
        """Validate patch and attempt automatic fixes."""
        # Normalize paths first
        normalized = self.validator.normalize_diff_paths(patch_content)
        
        # Validate format
        if not self.validator.validate_format(normalized):
            return {
                'success': False,
                'error': 'Invalid patch format - cannot auto-fix'
            }
        
        # Try to apply
        can_apply, error_msg = self.validator.can_apply(normalized)
        
        if can_apply:
            return {
                'success': True,
                'result': {'valid': True, 'patch': normalized}
            }
        
        # Attempt fixes
        # Fix 1: Try removing trailing whitespace
        fixed = '\n'.join(line.rstrip() for line in normalized.split('\n'))
        can_apply, error_msg = self.validator.can_apply(fixed)
        
        if can_apply:
            logger.info("✓ Auto-fixed patch (trailing whitespace)")
            return {
                'success': True,
                'result': {'valid': True, 'patch': fixed, 'fix_applied': 'trailing_whitespace'}
            }
        
        return {
            'success': False,
            'error': f'Could not auto-fix patch: {error_msg}'
        }
