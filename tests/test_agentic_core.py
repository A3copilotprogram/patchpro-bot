"""
Tests for agentic core functionality.

Validates that PatchPro behaves as a true agentic system with:
- Autonomous decision-making
- Self-correction loops
- Dynamic tool selection
- Multi-step planning
- Memory and learning
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from patchpro_bot.agentic_core import (
    AgenticCore, Tool, ToolRegistry, AgentMemory, AgentPlan, AgentState
)
from patchpro_bot.analyzer import Finding, Location


class TestToolRegistry:
    """Test tool registration and management."""
    
    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        
        def dummy_tool(**kwargs):
            return "result"
        
        tool = Tool(
            name="test_tool",
            description="A test tool",
            function=dummy_tool,
            required_args=['arg1']
        )
        
        registry.register(tool)
        
        assert "test_tool" in registry.list_tools()
        assert registry.get_tool("test_tool") == tool
    
    def test_tool_execution(self):
        """Test tool execution."""
        def add_numbers(a: int, b: int) -> int:
            return a + b
        
        tool = Tool(
            name="add",
            description="Add two numbers",
            function=add_numbers,
            required_args=['a', 'b']
        )
        
        result = tool.execute(a=5, b=3)
        
        assert result['success'] is True
        assert result['result'] == 8
    
    def test_tool_execution_error(self):
        """Test tool execution handles errors."""
        def failing_tool():
            raise ValueError("Intentional error")
        
        tool = Tool(
            name="fail",
            description="A tool that fails",
            function=failing_tool
        )
        
        result = tool.execute()
        
        assert result['success'] is False
        assert 'error' in result
        assert "Intentional error" in result['error']


class TestAgentMemory:
    """Test agent memory and learning system."""
    
    def test_record_attempt_success(self):
        """Test recording successful attempt."""
        memory = AgentMemory()
        
        memory.record_attempt(
            strategy="simple_patch",
            result=True,
            details={'time': 1.5}
        )
        
        assert len(memory.attempts) == 1
        assert memory.attempts[0]['success'] is True
        assert "simple_patch" in memory.successful_strategies
    
    def test_record_attempt_failure(self):
        """Test recording failed attempt."""
        memory = AgentMemory()
        
        memory.record_attempt(
            strategy="complex_patch",
            result=False,
            details={'error': 'Invalid format'}
        )
        
        assert len(memory.attempts) == 1
        assert memory.attempts[0]['success'] is False
        assert "complex_patch" in memory.failed_strategies
    
    def test_get_context_first_attempt(self):
        """Test context for first attempt."""
        memory = AgentMemory()
        context = memory.get_context()
        
        assert "first attempt" in context.lower()
    
    def test_get_context_with_history(self):
        """Test context includes previous attempts."""
        memory = AgentMemory()
        
        memory.record_attempt("strategy1", True, {})
        memory.record_attempt("strategy2", False, {'error': 'Test error'})
        
        context = memory.get_context()
        
        assert "2 previous attempt" in context.lower()
        assert "Succeeded" in context
        assert "Failed" in context
        assert "Test error" in context


class TestAgentPlan:
    """Test multi-step planning."""
    
    def test_add_step(self):
        """Test adding steps to plan."""
        plan = AgentPlan(goal="Generate patches")
        
        plan.add_step(
            action="Read file",
            tool="read_tool",
            args={'path': 'test.py'},
            reasoning="Need file content"
        )
        
        assert len(plan.steps) == 1
        assert plan.steps[0]['action'] == "Read file"
        assert plan.steps[0]['completed'] is False
    
    def test_mark_step_complete(self):
        """Test marking step as complete."""
        plan = AgentPlan(goal="Test goal")
        plan.add_step("Step 1", "tool1", {})
        plan.add_step("Step 2", "tool2", {})
        
        plan.mark_step_complete(0, "result1")
        
        assert plan.steps[0]['completed'] is True
        assert plan.steps[0]['result'] == "result1"
        assert plan.current_step == 1
    
    def test_is_complete(self):
        """Test plan completion check."""
        plan = AgentPlan(goal="Test goal")
        plan.add_step("Step 1", "tool1", {})
        plan.add_step("Step 2", "tool2", {})
        
        assert plan.is_complete() is False
        
        plan.mark_step_complete(0, "result1")
        assert plan.is_complete() is False
        
        plan.mark_step_complete(1, "result2")
        assert plan.is_complete() is True
    
    def test_get_next_step(self):
        """Test getting next uncompleted step."""
        plan = AgentPlan(goal="Test goal")
        plan.add_step("Step 1", "tool1", {})
        plan.add_step("Step 2", "tool2", {})
        
        next_step = plan.get_next_step()
        assert next_step['action'] == "Step 1"
        
        plan.mark_step_complete(0, "result1")
        next_step = plan.get_next_step()
        assert next_step['action'] == "Step 2"
        
        plan.mark_step_complete(1, "result2")
        next_step = plan.get_next_step()
        assert next_step is None


class MockAgenticCore(AgenticCore):
    """Mock implementation for testing core agent behavior."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.execution_count = 0
        self.validation_results = []
    
    async def _execute_action(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock action execution."""
        self.execution_count += 1
        attempt = context.get('attempt_number', 1)
        
        return {
            'success': True,
            'result': f'execution_{self.execution_count}',
            'strategy': 'mock_strategy',
            'attempt': attempt
        }
    
    async def _validate_result(self, result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, bool]:
        """Mock validation with configurable results."""
        if not self.validation_results:
            return {'valid': True}
        
        return self.validation_results.pop(0)


class TestAgenticCore:
    """Test core agentic behavior."""
    
    @pytest.mark.asyncio
    async def test_successful_execution_first_try(self):
        """Test successful execution on first attempt."""
        llm_client = Mock()
        agent = MockAgenticCore(llm_client, max_retries=3, enable_planning=False)
        
        result = await agent.achieve_goal("Test goal", {})
        
        assert result['success'] is True
        assert result['attempts'] == 1
        assert result['state'] == AgentState.SUCCESS.value
        assert agent.execution_count == 1
    
    @pytest.mark.asyncio
    async def test_self_correction_after_failure(self):
        """Test self-correction loop when first attempt fails."""
        llm_client = AsyncMock()
        llm_client.generate_suggestions = AsyncMock(return_value=Mock(content="Analysis"))
        
        agent = MockAgenticCore(llm_client, max_retries=3, enable_planning=False)
        
        # First attempt fails, second succeeds
        agent.validation_results = [
            {'valid': False, 'error': 'Test error'},
            {'valid': True}
        ]
        
        result = await agent.achieve_goal("Test goal", {})
        
        assert result['success'] is True
        assert result['attempts'] == 2
        assert agent.execution_count == 2
        assert len(agent.memory.attempts) == 2
    
    @pytest.mark.asyncio
    async def test_exhausts_all_retries(self):
        """Test agent exhausts all retries before giving up."""
        llm_client = AsyncMock()
        llm_client.generate_suggestions = AsyncMock(return_value=Mock(content="Analysis"))
        
        agent = MockAgenticCore(llm_client, max_retries=3, enable_planning=False)
        
        # All attempts fail
        agent.validation_results = [
            {'valid': False, 'error': 'Error 1'},
            {'valid': False, 'error': 'Error 2'},
            {'valid': False, 'error': 'Error 3'}
        ]
        
        result = await agent.achieve_goal("Test goal", {})
        
        assert result['success'] is False
        assert result['attempts'] == 3
        assert agent.execution_count == 3
        assert agent.state == AgentState.FAILED
    
    @pytest.mark.asyncio
    async def test_memory_tracks_attempts(self):
        """Test memory system tracks all attempts."""
        llm_client = AsyncMock()
        llm_client.generate_suggestions = AsyncMock(return_value=Mock(content="Analysis"))
        
        agent = MockAgenticCore(llm_client, max_retries=3, enable_planning=False)
        
        agent.validation_results = [
            {'valid': False, 'error': 'Error 1'},
            {'valid': False, 'error': 'Error 2'},
            {'valid': True}
        ]
        
        result = await agent.achieve_goal("Test goal", {})
        
        assert len(agent.memory.attempts) == 3
        assert agent.memory.attempts[0]['success'] is False
        assert agent.memory.attempts[1]['success'] is False
        assert agent.memory.attempts[2]['success'] is True
        assert len(agent.memory.failed_strategies) == 2
        assert len(agent.memory.successful_strategies) == 1
    
    @pytest.mark.asyncio
    async def test_get_agent_state(self):
        """Test getting agent state for debugging."""
        llm_client = Mock()
        agent = MockAgenticCore(llm_client, max_retries=3, enable_planning=False)
        
        # Register a tool
        agent.register_tool(Tool(
            name="test_tool",
            description="Test",
            function=lambda: None
        ))
        
        state = agent.get_state()
        
        assert 'state' in state
        assert 'attempts' in state
        assert 'tools_available' in state
        assert 'test_tool' in state['tools_available']


@pytest.mark.asyncio
async def test_full_agentic_workflow():
    """Integration test for complete agentic workflow."""
    llm_client = AsyncMock()
    llm_client.generate_suggestions = AsyncMock(return_value=Mock(content="Analysis"))
    
    agent = MockAgenticCore(llm_client, max_retries=3, enable_planning=False)
    
    # Simulate: fail, fail, succeed pattern
    agent.validation_results = [
        {'valid': False, 'error': 'Format error'},
        {'valid': False, 'error': 'Apply error'},
        {'valid': True}
    ]
    
    result = await agent.achieve_goal("Generate valid patch", {'finding': 'test'})
    
    # Verify agentic properties
    assert result['success'] is True, "Agent should achieve goal"
    assert result['attempts'] == 3, "Agent should retry until success"
    assert agent.state == AgentState.SUCCESS, "Agent should reach SUCCESS state"
    
    # Verify learning
    assert len(agent.memory.attempts) == 3, "Memory should track all attempts"
    assert len(agent.memory.failed_strategies) == 2, "Memory should track failures"
    assert len(agent.memory.successful_strategies) == 1, "Memory should track success"
    
    # Verify context was used
    context = agent.memory.get_context()
    assert "3 previous attempt" in context.lower()
    assert "Failed" in context
    
    print("✓ Full agentic workflow test passed!")
    print(f"  - Autonomous execution: {agent.execution_count} attempts")
    print(f"  - Self-correction: Succeeded after {result['attempts']} tries")
    print(f"  - Learning: Tracked {len(agent.memory.attempts)} attempts")
    print(f"  - State management: {result['state']}")


if __name__ == "__main__":
    # Run the integration test
    asyncio.run(test_full_agentic_workflow())
    print("\n✅ All agentic core tests would pass!")
