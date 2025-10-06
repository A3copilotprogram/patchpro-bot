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
from patchpro_bot.telemetry import PatchTracer
from patchpro_bot.patch_validator import PatchValidator

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
        enable_planning: bool = True,
        enable_tracing: bool = True
    ):
        """Initialize the agentic patch generator.
        
        Args:
            llm_client: LLM client for generation
            repo_path: Path to repository
            max_retries: Maximum retry attempts
            enable_planning: Enable planning mode
            enable_tracing: Enable telemetry/trace logging
        """
        super().__init__(llm_client, max_retries, enable_planning)
        
        self.repo_path = repo_path
        self.context_reader = FindingContextReader(context_lines=5)
        self.prompt_builder = PromptBuilder()
        self.response_parser = ResponseParser()
        self.validator = DiffValidator()
        self.patch_validator = PatchValidator()  # NEW: For fixing corrupt hunks
        
        # Telemetry
        self.enable_tracing = enable_tracing
        self.tracer = PatchTracer(trace_dir=repo_path / ".patchpro" / "traces") if enable_tracing else None
        
        # Register specialized tools
        self._register_patch_tools()
        
        if enable_tracing:
            logger.info(f"Initialized AgenticPatchGeneratorV2 for {repo_path} (tracing ENABLED)")
        else:
            logger.info(f"Initialized AgenticPatchGeneratorV2 for {repo_path} (tracing DISABLED)")
    
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
            
            # Pass context as explicit parameter instead of unpacking
            # This allows feedback to flow through the retry loop
            result = await tool.function(context=context)
            
            # Record attempt in memory
            self.memory.record_attempt(
                strategy=strategy,
                result=result['success'],
                details=result
            )
            
            if result['success']:
                logger.info(f"✓ Strategy {strategy} succeeded on attempt {attempt}")
                return result
            
            # Failed - analyze and provide feedback for next attempt
            error_msg = result.get('error', 'Unknown error')
            validation_feedback = result.get('validation_feedback', [])
            
            logger.warning(f"✗ Strategy {strategy} failed: {error_msg}")
            
            if attempt < self.max_retries:
                # Add validation feedback to context for next attempt
                if validation_feedback:
                    context['previous_errors'] = validation_feedback
                    context['attempt_number'] = attempt + 1
                    logger.info(f"Retry {attempt + 1} with feedback: {validation_feedback[:100]}")
                
                # Try alternative strategy on first failure
                if attempt == 1 and strategy == "generate_batch_patch":
                    # Batch failed, try individual
                    strategy = "generate_single_patch"
                    # Convert batch context to single
                    if 'findings' in context and context['findings']:
                        context = {'finding': context['findings'][0]}
                        if validation_feedback:
                            context['previous_errors'] = validation_feedback
                        logger.info("Switching to single-patch strategy with error feedback")
        
        return {'success': False, 'error': 'Exhausted all retries'}
    
    async def _generate_single_patch(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate patch for single finding using PROVEN Issue #13 approach.
        
        This is the 100% success rate strategy.
        """
        import time
        
        try:
            # Extract finding from context
            finding = context.get('finding')
            if not finding:
                return {'success': False, 'error': 'Missing finding in context'}
            
            # Start tracing if enabled
            retry_attempt = context.get('attempt_number', 1)
            previous_errors = context.get('previous_errors', [])
            
            # Use context manager properly
            if self.enable_tracing and self.tracer:
                with self.tracer.trace_patch_generation(
                    finding=finding,
                    strategy="generate_single_patch",
                    retry_attempt=retry_attempt,
                    previous_errors=previous_errors
                ) as trace_ctx:
                    return await self._generate_single_patch_with_tracing(
                        finding=finding,
                        context=context,
                        retry_attempt=retry_attempt,
                        previous_errors=previous_errors,
                        trace_ctx=trace_ctx
                    )
            else:
                # No tracing - just generate
                return await self._generate_single_patch_with_tracing(
                    finding=finding,
                    context=context,
                    retry_attempt=retry_attempt,
                    previous_errors=previous_errors,
                    trace_ctx=None
                )
                
        except Exception as e:
            logger.error(f"Single patch generation failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _generate_single_patch_with_tracing(
        self,
        finding: AnalysisFinding,
        context: Dict[str, Any],
        retry_attempt: int,
        previous_errors: List[str],
        trace_ctx: Optional[Any]
    ) -> Dict[str, Any]:
        """Internal method that does the actual patch generation with optional tracing."""
        import time
        
        try:
            
            # Group into file_fixes format that PromptBuilder expects
            file_fixes = {finding.location.file: [finding]}
            
            # Use PROVEN prompt builder from Issue #13
            prompt = self.prompt_builder.build_unified_diff_prompt_with_context(
                file_fixes=file_fixes,
                repo_path=str(self.repo_path)
            )
            
            # Add previous error feedback to prompt if available (agentic self-correction)
            if previous_errors:
                attempt = retry_attempt
                error_text = '\n'.join(f"  - {err}" for err in previous_errors)
                feedback_prompt = f"""
IMPORTANT: Previous attempt #{attempt-1} failed validation with these errors:
{error_text}

Please carefully address these issues in your patch. Common problems:
- Empty additions ('+' with no content) - always include the actual code
- Wrong line numbers - account for previous changes in multi-hunk patches
- Missing context - include enough surrounding lines (typically 3)
- Corrupted hunks - ensure proper unified diff format with @@ headers

Generate a corrected patch that will pass git apply validation.
"""
                prompt = feedback_prompt + "\n\n" + prompt
            
            # Record prompt in trace
            if trace_ctx:
                trace_ctx.set_prompt(prompt, self.prompt_builder.system_prompt)
            
            # Call LLM with timing
            start_time = time.time()
            response = await self.llm_client.generate_response(
                prompt=prompt,
                system_prompt=self.prompt_builder.system_prompt,
                use_json_mode=False
            )
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Calculate cost (gpt-4o-mini pricing: $0.15/1M input, $0.60/1M output)
            prompt_tokens = response.usage.get('prompt_tokens', 0) if response.usage else 0
            completion_tokens = response.usage.get('completion_tokens', 0) if response.usage else 0
            total_tokens = prompt_tokens + completion_tokens
            cost_usd = (prompt_tokens * 0.15 / 1_000_000) + (completion_tokens * 0.60 / 1_000_000)
            
            # Record LLM response in trace
            if trace_ctx:
                trace_ctx.set_llm_response(
                    response=response.content,
                    model=response.model,
                    tokens_used=total_tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    cost_usd=cost_usd
                )
            
            # Parse with PROVEN parser from Issue #13
            parsed = self.response_parser.parse_response(
                response.content,
                expected_type=ResponseType.DIFF_PATCHES
            )
            
            if not parsed.diff_patches:
                if trace_ctx:
                    trace_ctx.set_patch(None)
                    trace_ctx.set_validation(False, ["No patches parsed from LLM response"])
                return {'success': False, 'error': 'No patches parsed from LLM response'}
            
            # Validate patches with git apply and collect feedback
            valid_patches = []
            validation_feedback = []
            
            for patch in parsed.diff_patches:
                # First check format
                is_valid_format, format_errors = self.validator.validate_format(patch.diff_content)
                if not is_valid_format:
                    feedback = f"Format errors in {patch.file_path}: {', '.join(format_errors)}"
                    validation_feedback.append(feedback)
                    logger.warning(feedback)
                    continue
                
                # NEW: Try to fix corrupt hunk headers before git apply
                try:
                    file_path = self.repo_path / patch.file_path
                    logger.debug(f"Validating patch for {patch.file_path} at {file_path}")
                    
                    fixed_patch_content, fix_metrics = self.patch_validator.validate_and_fix_patch(
                        patch.diff_content,
                        file_path
                    )
                    
                    logger.debug(f"Validation result: {fix_metrics}")
                    
                    if fix_metrics['was_fixed']:
                        logger.info(f"🔧 Fixed corrupt hunk headers in {patch.file_path}: {fix_metrics['fixes_applied']}")
                        patch.diff_content = fixed_patch_content  # Use fixed version
                    elif fix_metrics['errors']:
                        logger.warning(f"⚠️  Could not fix patch for {patch.file_path}: {fix_metrics['errors']}")
                except Exception as e:
                    logger.error(f"❌ Patch validation error for {patch.file_path}: {e}", exc_info=True)
                
                # Then check if git can apply it (the real test)
                can_apply, apply_error = self.validator.can_apply(
                    patch.diff_content,
                    str(self.repo_path)
                )
                
                if can_apply:
                    valid_patches.append(patch)
                    logger.info(f"✓ Patch for {patch.file_path} validated successfully")
                else:
                    feedback = f"Git apply failed for {patch.file_path}: {apply_error.strip()}"
                    validation_feedback.append(feedback)
                    logger.warning(feedback)
            
            # Record validation results in trace
            if trace_ctx:
                if valid_patches:
                    trace_ctx.set_patch(valid_patches[0].diff_content)
                    trace_ctx.set_validation(True, [])
                else:
                    trace_ctx.set_patch(parsed.diff_patches[0].diff_content if parsed.diff_patches else None)
                    trace_ctx.set_validation(False, validation_feedback)
            
            if not valid_patches:
                # Return detailed feedback for agent to use in retry
                error_detail = '; '.join(validation_feedback) if validation_feedback else 'All patches failed validation'
                return {
                    'success': False,
                    'error': f'No patches passed git apply validation. {error_detail}',
                    'validation_feedback': validation_feedback
                }
            
            return {'success': True, 'result': {'patches': valid_patches}}
            
        except Exception as e:
            # Record exception in trace
            if trace_ctx:
                trace_ctx.set_validation(False, [str(e)])
            
            logger.error(f"Inner patch generation failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _generate_batch_patch(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate unified patch for multiple findings in same file."""
        try:
            # Extract findings from context
            findings = context.get('findings', [])
            if not findings:
                return {'success': False, 'error': 'Missing findings in context'}
            
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
            
            # Add previous error feedback if available (agentic self-correction)
            if 'previous_errors' in context:
                attempt = context.get('attempt_number', 2)
                error_text = '\n'.join(f"  - {err}" for err in context['previous_errors'])
                feedback_prompt = f"""
IMPORTANT: Previous attempt #{attempt-1} failed validation with these errors:
{error_text}

Please carefully address these issues in your batch patch. Common problems:
- Empty additions ('+' with no content) - always include the actual code
- Wrong line numbers - account for previous changes in multi-hunk patches
- Missing context - include enough surrounding lines (typically 3)
- Corrupted hunks - ensure proper unified diff format with @@ headers

Generate a corrected unified diff patch that will pass git apply validation.
"""
                prompt = feedback_prompt + "\n\n" + prompt
            
            # Call LLM
            response = await self.llm_client.generate_response(
                prompt=prompt,
                system_prompt=self.prompt_builder.system_prompt,
                use_json_mode=False
            )
            
            # Parse
            parsed = self.response_parser.parse_response(
                response.content,
                expected_type=ResponseType.DIFF_PATCHES
            )
            
            if not parsed.diff_patches:
                return {'success': False, 'error': 'No patches parsed from LLM response'}
            
            # Validate patches with git apply and collect feedback
            valid_patches = []
            validation_feedback = []
            
            for patch in parsed.diff_patches:
                # First check format
                is_valid_format, format_errors = self.validator.validate_format(patch.diff_content)
                if not is_valid_format:
                    feedback = f"Format errors in {patch.file_path}: {', '.join(format_errors)}"
                    validation_feedback.append(feedback)
                    logger.warning(feedback)
                    continue
                
                # NEW: Try to fix corrupt hunk headers before git apply
                try:
                    file_path = self.repo_path / patch.file_path
                    logger.debug(f"Validating patch for {patch.file_path} at {file_path}")
                    
                    fixed_patch_content, fix_metrics = self.patch_validator.validate_and_fix_patch(
                        patch.diff_content,
                        file_path
                    )
                    
                    logger.debug(f"Validation result: {fix_metrics}")
                    
                    if fix_metrics['was_fixed']:
                        logger.info(f"🔧 Fixed corrupt hunk headers in {patch.file_path}: {fix_metrics['fixes_applied']}")
                        patch.diff_content = fixed_patch_content  # Use fixed version
                    elif fix_metrics['errors']:
                        logger.warning(f"⚠️  Could not fix patch for {patch.file_path}: {fix_metrics['errors']}")
                except Exception as e:
                    logger.error(f"❌ Patch validation error for {patch.file_path}: {e}", exc_info=True)
                
                # Then check if git can apply it (the real test)
                can_apply, apply_error = self.validator.can_apply(
                    patch.diff_content,
                    str(self.repo_path)
                )
                
                if can_apply:
                    valid_patches.append(patch)
                    logger.info(f"✓ Batch patch for {patch.file_path} validated successfully")
                else:
                    feedback = f"Git apply failed for {patch.file_path}: {apply_error.strip()}"
                    validation_feedback.append(feedback)
                    logger.warning(feedback)
            
            if not valid_patches:
                # Return detailed feedback for agent to use in retry
                error_detail = '; '.join(validation_feedback) if validation_feedback else 'All patches failed validation'
                return {
                    'success': False,
                    'error': f'No patches passed git apply validation. {error_detail}',
                    'validation_feedback': validation_feedback
                }
            
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
