"""
Agentic core for PatchPro - provides autonomous behavior, self-correction, and tool use.

This module transforms PatchPro from an automation pipeline into a true agentic system with:
- Autonomous decision-making
- Self-correction loops
- Dynamic tool selection
- Multi-step planning
- Learning from failures
"""

import logging
import json
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """States in the agent execution lifecycle."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    CORRECTING = "correcting"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class AgentMemory:
    """Memory system for agent to learn from past attempts."""
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    successful_strategies: List[str] = field(default_factory=list)
    failed_strategies: List[str] = field(default_factory=list)
    learned_patterns: Dict[str, Any] = field(default_factory=dict)
    
    def record_attempt(self, strategy: str, result: bool, details: Dict[str, Any]):
        """Record an attempt and its outcome."""
        self.attempts.append({
            'strategy': strategy,
            'success': result,
            'details': details,
            'attempt_number': len(self.attempts) + 1
        })
        
        if result:
            self.successful_strategies.append(strategy)
        else:
            self.failed_strategies.append(strategy)
    
    def get_context(self) -> str:
        """Get memory context for LLM prompting."""
        if not self.attempts:
            return "This is your first attempt."
        
        context = f"You have made {len(self.attempts)} previous attempt(s):\n"
        for attempt in self.attempts[-3:]:  # Last 3 attempts
            status = "✓ Succeeded" if attempt['success'] else "✗ Failed"
            context += f"- Attempt {attempt['attempt_number']}: {status}\n"
            context += f"  Strategy: {attempt['strategy']}\n"
            if not attempt['success'] and 'error' in attempt['details']:
                context += f"  Error: {attempt['details']['error']}\n"
        
        if self.successful_strategies:
            context += f"\nSuccessful strategies: {', '.join(set(self.successful_strategies))}\n"
        
        return context


@dataclass
class Tool:
    """Represents a tool the agent can use."""
    name: str
    description: str
    function: Callable
    required_args: List[str] = field(default_factory=list)
    optional_args: List[str] = field(default_factory=list)
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given arguments."""
        try:
            result = self.function(**kwargs)
            return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"Tool {self.name} failed: {e}")
            return {'success': False, 'error': str(e)}


class ToolRegistry:
    """Registry of available tools for the agent."""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        """Register a new tool."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all available tool names."""
        return list(self.tools.keys())
    
    def get_tools_description(self) -> str:
        """Get formatted description of all tools for LLM."""
        desc = "Available tools:\n"
        for name, tool in self.tools.items():
            desc += f"- {name}: {tool.description}\n"
            if tool.required_args:
                desc += f"  Required args: {', '.join(tool.required_args)}\n"
        return desc


@dataclass
class AgentPlan:
    """A multi-step plan for achieving a goal."""
    goal: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    
    def add_step(self, action: str, tool: str, args: Dict[str, Any], reasoning: str = ""):
        """Add a step to the plan."""
        self.steps.append({
            'step_number': len(self.steps) + 1,
            'action': action,
            'tool': tool,
            'args': args,
            'reasoning': reasoning,
            'completed': False,
            'result': None
        })
    
    def mark_step_complete(self, step_number: int, result: Any):
        """Mark a step as completed with its result."""
        if 0 <= step_number < len(self.steps):
            self.steps[step_number]['completed'] = True
            self.steps[step_number]['result'] = result
            self.current_step = step_number + 1
    
    def is_complete(self) -> bool:
        """Check if all steps are completed."""
        return all(step['completed'] for step in self.steps)
    
    def get_next_step(self) -> Optional[Dict[str, Any]]:
        """Get the next uncompleted step."""
        for step in self.steps:
            if not step['completed']:
                return step
        return None


class AgenticCore:
    """
    Core agentic system with autonomous behavior.
    
    Features:
    - Self-correction loops
    - Dynamic tool selection
    - Multi-step planning
    - Memory and learning
    - Goal-oriented behavior
    """
    
    def __init__(self, llm_client, max_retries: int = 3, enable_planning: bool = True):
        """
        Initialize the agentic core.
        
        Args:
            llm_client: LLM client for agent reasoning
            max_retries: Maximum retry attempts for self-correction
            enable_planning: Whether to use multi-step planning
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.enable_planning = enable_planning
        
        self.state = AgentState.IDLE
        self.memory = AgentMemory()
        self.tool_registry = ToolRegistry()
        self.current_plan: Optional[AgentPlan] = None
        
        logger.info(f"Initialized AgenticCore (max_retries={max_retries}, planning={enable_planning})")
    
    def register_tool(self, tool: Tool):
        """Register a tool for the agent to use."""
        self.tool_registry.register(tool)
    
    async def achieve_goal(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Autonomously achieve a goal with planning and self-correction.
        
        Args:
            goal: High-level goal description
            context: Context information for the goal
            
        Returns:
            Result dict with success status and details
        """
        logger.info(f"Agent goal: {goal}")
        self.state = AgentState.PLANNING
        
        # Create or refine plan
        if self.enable_planning:
            plan = await self._create_plan(goal, context)
            self.current_plan = plan
            
            # Execute plan step by step
            return await self._execute_plan(plan, context)
        else:
            # Direct execution without planning
            return await self._execute_with_retry(goal, context)
    
    async def _create_plan(self, goal: str, context: Dict[str, Any]) -> AgentPlan:
        """Use LLM to create a multi-step plan."""
        logger.info("Creating execution plan...")
        
        prompt = f"""You are an autonomous agent creating a plan to achieve a goal.

Goal: {goal}

Context:
{json.dumps(context, indent=2)}

{self.tool_registry.get_tools_description()}

{self.memory.get_context()}

Create a detailed step-by-step plan. For each step, specify:
1. Action description
2. Tool to use
3. Arguments for the tool
4. Reasoning for this step

Return a JSON plan with this structure:
{{
  "steps": [
    {{
      "action": "Description of what to do",
      "tool": "tool_name",
      "args": {{"arg1": "value1"}},
      "reasoning": "Why this step is needed"
    }}
  ]
}}

Be strategic and adaptive based on previous attempts."""
        
        try:
            response = await self.llm_client.generate_suggestions(
                prompt=prompt,
                system_prompt="You are a strategic planning agent. Create efficient, goal-oriented plans."
            )
            
            plan_data = json.loads(response.content)
            plan = AgentPlan(goal=goal)
            
            for step_data in plan_data.get('steps', []):
                plan.add_step(
                    action=step_data['action'],
                    tool=step_data['tool'],
                    args=step_data['args'],
                    reasoning=step_data.get('reasoning', '')
                )
            
            logger.info(f"Created plan with {len(plan.steps)} steps")
            return plan
            
        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            # Fallback: simple single-step plan
            plan = AgentPlan(goal=goal)
            plan.add_step(
                action=goal,
                tool="generate_patch",
                args=context,
                reasoning="Direct execution fallback"
            )
            return plan
    
    async def _execute_plan(self, plan: AgentPlan, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a multi-step plan."""
        self.state = AgentState.EXECUTING
        
        while not plan.is_complete():
            step = plan.get_next_step()
            if not step:
                break
            
            logger.info(f"Executing step {step['step_number']}: {step['action']}")
            
            # Get tool
            tool = self.tool_registry.get_tool(step['tool'])
            if not tool:
                logger.error(f"Tool not found: {step['tool']}")
                return {
                    'success': False,
                    'error': f"Tool '{step['tool']}' not available",
                    'state': self.state.value
                }
            
            # Execute tool
            result = tool.execute(**step['args'])
            
            if result['success']:
                plan.mark_step_complete(step['step_number'] - 1, result['result'])
                logger.info(f"✓ Step {step['step_number']} completed")
            else:
                logger.warning(f"✗ Step {step['step_number']} failed: {result.get('error')}")
                
                # Try to recover or replan
                recovery_result = await self._handle_step_failure(step, result, context)
                if recovery_result['success']:
                    plan.mark_step_complete(step['step_number'] - 1, recovery_result['result'])
                else:
                    self.state = AgentState.FAILED
                    return recovery_result
        
        self.state = AgentState.SUCCESS
        return {
            'success': True,
            'plan_completed': True,
            'steps_executed': len(plan.steps),
            'state': self.state.value
        }
    
    async def _execute_with_retry(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute goal with self-correction loop.
        
        This is the core agentic behavior: try, validate, learn, retry.
        """
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Attempt {attempt}/{self.max_retries}: {goal}")
            self.state = AgentState.EXECUTING
            
            # Add memory context to guide the attempt
            enhanced_context = {
                **context,
                'memory_context': self.memory.get_context(),
                'attempt_number': attempt
            }
            
            # Execute primary action
            result = await self._execute_action(goal, enhanced_context)
            
            # Validate result
            self.state = AgentState.VALIDATING
            validation = await self._validate_result(result, context)
            
            if validation['valid']:
                # Success!
                self.state = AgentState.SUCCESS
                self.memory.record_attempt(
                    strategy=result.get('strategy', 'default'),
                    result=True,
                    details={'attempt': attempt}
                )
                logger.info(f"✓ Goal achieved on attempt {attempt}")
                return {
                    'success': True,
                    'result': result,
                    'attempts': attempt,
                    'state': self.state.value
                }
            else:
                # Failed validation - learn and retry
                self.state = AgentState.CORRECTING
                self.memory.record_attempt(
                    strategy=result.get('strategy', 'default'),
                    result=False,
                    details={
                        'attempt': attempt,
                        'error': validation.get('error', 'Unknown error')
                    }
                )
                logger.warning(f"✗ Attempt {attempt} failed: {validation.get('error')}")
                
                # Analyze failure for next attempt
                if attempt < self.max_retries:
                    await self._analyze_failure(result, validation, context)
        
        # All retries exhausted
        self.state = AgentState.FAILED
        logger.error(f"Failed to achieve goal after {self.max_retries} attempts")
        return {
            'success': False,
            'error': 'Maximum retries exceeded',
            'attempts': self.max_retries,
            'state': self.state.value,
            'memory': self.memory.attempts
        }
    
    async def _execute_action(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the primary action."""
        # This will be overridden by specific implementations
        # For now, it's a placeholder that subclasses will implement
        raise NotImplementedError("Subclass must implement _execute_action")
    
    async def _validate_result(self, result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, bool]:
        """Validate the result of an action."""
        # This will be overridden by specific implementations
        raise NotImplementedError("Subclass must implement _validate_result")
    
    async def _analyze_failure(self, result: Dict[str, Any], validation: Dict[str, Any], context: Dict[str, Any]):
        """Analyze why something failed and learn from it."""
        logger.info("Analyzing failure to improve next attempt...")
        
        # Use LLM to understand the failure
        prompt = f"""Analyze this failure and suggest how to fix it:

Result: {json.dumps(result, indent=2)}
Validation Error: {validation.get('error', 'Unknown')}
Context: {json.dumps(context, indent=2)}

Previous attempts:
{self.memory.get_context()}

What went wrong and how should we adjust the approach for the next attempt?"""
        
        try:
            response = await self.llm_client.generate_suggestions(
                prompt=prompt,
                system_prompt="You are an error analysis expert. Identify root causes and suggest corrections."
            )
            
            analysis = response.content
            logger.info(f"Failure analysis: {analysis[:200]}...")
            
            # Store insight in memory
            self.memory.learned_patterns['last_analysis'] = analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze error: {e}")
    
    async def _handle_step_failure(self, step: Dict[str, Any], result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failure of a plan step - try to recover or replan."""
        logger.info(f"Attempting to recover from step failure...")
        
        # Strategy 1: Retry the same step
        tool = self.tool_registry.get_tool(step['tool'])
        if tool:
            retry_result = tool.execute(**step['args'])
            if retry_result['success']:
                logger.info("✓ Step recovery successful")
                return retry_result
        
        # Strategy 2: Ask LLM for alternative approach
        prompt = f"""A step in your plan failed. Find an alternative approach.

Failed step: {step['action']}
Error: {result.get('error')}
Available tools: {self.tool_registry.list_tools()}

What's an alternative way to accomplish: {step['action']}?
Respond with JSON: {{"tool": "tool_name", "args": {{}}, "reasoning": "why this works"}}"""
        
        try:
            response = await self.llm_client.generate_suggestions(
                prompt=prompt,
                system_prompt="You are a problem-solving agent. Find alternative solutions."
            )
            
            alternative = json.loads(response.content)
            alt_tool = self.tool_registry.get_tool(alternative['tool'])
            
            if alt_tool:
                logger.info(f"Trying alternative: {alternative['reasoning']}")
                return alt_tool.execute(**alternative['args'])
        
        except Exception as e:
            logger.error(f"Could not find alternative: {e}")
        
        return {'success': False, 'error': 'No recovery strategy found'}
    
    def get_state(self) -> Dict[str, Any]:
        """Get current agent state for debugging."""
        return {
            'state': self.state.value,
            'attempts': len(self.memory.attempts),
            'successful_strategies': self.memory.successful_strategies,
            'failed_strategies': self.memory.failed_strategies,
            'tools_available': self.tool_registry.list_tools(),
            'current_plan': self.current_plan.goal if self.current_plan else None
        }
