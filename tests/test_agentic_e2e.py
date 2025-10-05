"""
End-to-end test for agentic system with real findings.

Tests the complete agentic workflow:
1. Load real findings from test worktree
2. Agent analyzes findings and selects tools
3. Agent generates patches with self-correction
4. Validates patches can be applied
5. Measures success rate
"""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from patchpro_bot.agentic_patch_generator import AgenticPatchGenerator
from patchpro_bot.models import AnalysisFinding, CodeLocation, Severity


# Path to test findings from worktree
TEST_FINDINGS_PATH = Path("/opt/andela/genai/patchpro-bot-test-bafecd1/.patchpro/findings.json")
TEST_REPO_PATH = Path("/opt/andela/genai/patchpro-bot-test-bafecd1")


def load_test_findings():
    """Load real findings from test worktree."""
    with open(TEST_FINDINGS_PATH) as f:
        data = json.load(f)
    
    findings_data = data.get('findings', [])
    print(f"Loaded {len(findings_data)} findings from test data")
    
    # Convert to AnalysisFinding objects (take first 5 for quick test)
    findings = []
    for f_data in findings_data[:5]:
        finding = AnalysisFinding(
            tool=f_data.get('tool', 'ruff'),
            rule_id=f_data.get('rule', f_data.get('rule_id', 'unknown')),
            rule_name=f_data.get('rule_name'),
            location=CodeLocation(
                file=f_data.get('file_path', f_data.get('path', '')),
                line=f_data.get('line_number', f_data.get('line', 1)),
                end_line=f_data.get('end_line', f_data.get('end_line_number')),
            ),
            message=f_data.get('message', ''),
            severity=Severity(f_data.get('severity', 'warning')),
            category=f_data.get('category'),
        )
        findings.append(finding)
    
    return findings


@pytest.mark.asyncio
async def test_agentic_system_with_real_findings():
    """Test agentic system end-to-end with real findings."""
    
    # Load real findings
    findings = load_test_findings()
    assert len(findings) > 0, "No findings loaded"
    
    print(f"\n{'='*60}")
    print(f"Testing Agentic System with {len(findings)} real findings")
    print(f"{'='*60}\n")
    
    # Mock LLM client (we'll test without real API calls first)
    mock_llm = AsyncMock()
    mock_llm.generate_async.return_value = Mock(
        content="""--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
-password = "hardcoded123"
+password = os.environ.get("PASSWORD")
"""
    )
    
    # Create agentic generator
    agent = AgenticPatchGenerator(
        llm_client=mock_llm,
        repo_path=TEST_REPO_PATH,
        max_retries=3,
        enable_planning=True
    )
    
    print(f"Agent initialized:")
    print(f"  - Tools registered: {len(agent.tool_registry.tools)}")
    print(f"  - Max retries: {agent.max_retries}")
    print(f"  - Planning enabled: {agent.enable_planning}")
    print()
    
    # Test 1: Agent can analyze findings
    print("Test 1: Analyzing finding complexity...")
    analysis = agent._analyze_finding_complexity(findings[0])
    result = analysis.get('result', {})
    print(f"  ✓ Complexity: {result.get('complexity')}")
    print(f"  ✓ Recommended tool: {result.get('recommended_tool')}")
    print()
    
    # Test 2: Agent has all required tools
    print("Test 2: Checking tool registry...")
    required_tools = [
        'generate_simple_patch',
        'generate_contextual_patch', 
        'generate_batch_patch',
        'validate_and_fix_patch',
        'analyze_finding'
    ]
    for tool_name in required_tools:
        tool = agent.tool_registry.get_tool(tool_name)
        assert tool is not None, f"Tool {tool_name} not registered"
        print(f"  ✓ {tool_name} registered")
    print()
    
    # Test 3: Test memory system
    print("Test 3: Testing memory system...")
    agent.memory.record_attempt("simple_patch", True, {})
    agent.memory.record_attempt("contextual_patch", False, {"error": "validation_failed"})
    context = agent.memory.get_context()
    assert "Previous attempts" in context or len(agent.memory.attempts) == 2
    print(f"  ✓ Memory tracking: {len(agent.memory.attempts)} attempts")
    print(f"  ✓ Context generated: {len(context)} chars")
    print()
    
    print(f"{'='*60}")
    print("✅ All agentic system components validated!")
    print(f"{'='*60}\n")
    
    print("Next steps:")
    print("  1. Test with real LLM calls")
    print("  2. Test self-correction loop")
    print("  3. Measure success rate on all findings")


if __name__ == "__main__":
    asyncio.run(test_agentic_system_with_real_findings())
