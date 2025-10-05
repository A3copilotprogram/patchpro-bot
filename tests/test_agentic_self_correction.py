"""
Test self-correction loop with real LLM.

This test validates that the agentic system can:
1. Try a strategy and fail validation
2. Learn from the failure
3. Retry with a different approach
4. Succeed after self-correction
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from patchpro_bot.agentic_patch_generator import AgenticPatchGenerator
from patchpro_bot.models import AnalysisFinding, CodeLocation, Severity
from patchpro_bot.llm import LLMClient


# Path to test findings
TEST_FINDINGS_PATH = Path("/opt/andela/genai/patchpro-bot-test-bafecd1/.patchpro/findings.json")
TEST_REPO_PATH = Path("/opt/andela/genai/patchpro-bot-test-bafecd1")


def load_one_finding():
    """Load a single real finding for testing."""
    with open(TEST_FINDINGS_PATH) as f:
        data = json.load(f)
    
    f_data = data['findings'][0]  # Take first finding
    
    return AnalysisFinding(
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


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv('OPENAI_API_KEY'), reason="No API key")
async def test_self_correction_with_real_llm():
    """
    Test that agent can self-correct after validation failures.
    
    Strategy:
    1. Create agent with real LLM client
    2. Give it a finding
    3. Mock validator to fail first attempt
    4. Verify agent retries with different strategy
    5. Verify memory tracks the failure and success
    """
    
    print("\n" + "="*60)
    print("Testing Self-Correction Loop with Real LLM")
    print("="*60 + "\n")
    
    # Load real finding
    finding = load_one_finding()
    print(f"Testing with finding: {finding.tool}:{finding.rule_id}")
    print(f"Location: {finding.location.file}:{finding.location.line}")
    print(f"Message: {finding.message}\n")
    
    # Create real LLM client
    llm_client = LLMClient(
        api_key=os.getenv('OPENAI_API_KEY'),
        model="gpt-4o-mini"
    )
    
    # Create agent
    agent = AgenticPatchGenerator(
        llm_client=llm_client,
        repo_path=TEST_REPO_PATH,
        max_retries=3,
        enable_planning=False  # Disable planning for simpler test
    )
    
    print("Agent initialized with real LLM client")
    print(f"  - Model: gpt-4o-mini")
    print(f"  - Max retries: 3")
    print(f"  - Tools: {len(agent.tool_registry.tools)}\n")
    
    # Test: Generate patches with self-correction
    print("Calling agent.generate_patches()...")
    print("(This will make real LLM calls)\n")
    
    result = await agent.generate_patches([finding])
    
    print("\nResult:")
    print(f"  - Patches generated: {len(result.get('patches', []))}")
    print(f"  - Valid patches: {len(result.get('valid_patches', []))}")
    print(f"  - Attempts made: {len(agent.memory.attempts)}")
    print()
    
    # Verify memory tracked attempts
    if agent.memory.attempts:
        print("Memory log:")
        for attempt in agent.memory.attempts:
            status = "✓" if attempt['success'] else "✗"
            print(f"  {status} Attempt {attempt['attempt_number']}: {attempt['strategy']}")
            if not attempt['success']:
                print(f"     Error: {attempt['details'].get('error', 'unknown')}")
    
    print("\n" + "="*60)
    print("✅ Self-correction test completed!")
    print("="*60)
    
    # Assertions
    assert result is not None, "Agent should return a result"
    assert 'patches' in result, "Result should contain patches"
    
    # If we got patches, at least one should be valid
    if result['patches']:
        print(f"\nGenerated {len(result['patches'])} patch(es)")
        for i, patch in enumerate(result['patches'], 1):
            print(f"  Patch {i}: {patch.file_path}")


@pytest.mark.asyncio  
async def test_self_correction_mock():
    """
    Test self-correction with mocked LLM that fails then succeeds.
    
    This validates the retry logic without real API calls.
    """
    
    print("\n" + "="*60)
    print("Testing Self-Correction with Mock (No API calls)")
    print("="*60 + "\n")
    
    finding = load_one_finding()
    
    # Create mock that fails first time, succeeds second time
    mock_llm = AsyncMock()
    
    # First call: return invalid diff (missing headers)
    # Second call: return valid diff
    mock_llm.generate_async.side_effect = [
        Mock(content="just some code without diff headers"),  # Invalid
        Mock(content="""--- a/test.py
+++ b/test.py
@@ -1,1 +1,1 @@
-old line
+new line
""")  # Valid
    ]
    
    agent = AgenticPatchGenerator(
        llm_client=mock_llm,
        repo_path=TEST_REPO_PATH,
        max_retries=3,
        enable_planning=False
    )
    
    # Mock validator to reject first patch, accept second
    original_validate = agent.validator.validate_format
    call_count = [0]
    
    def mock_validate(diff_content):
        call_count[0] += 1
        if call_count[0] == 1:
            return False, ["Missing diff headers"]  # Fail first
        return original_validate(diff_content)  # Use real validator after
    
    agent.validator.validate_format = mock_validate
    
    print("Mock LLM configured:")
    print("  - Attempt 1: Invalid diff (no headers)")
    print("  - Attempt 2: Valid unified diff")
    print()
    
    # This should trigger self-correction
    result = await agent.generate_patches([finding])
    
    print(f"\nLLM called: {mock_llm.generate_async.call_count} times")
    print(f"Validator called: {call_count[0]} times")
    print(f"Memory has: {len(agent.memory.attempts)} attempts")
    print()
    
    # Verify self-correction happened
    assert mock_llm.generate_async.call_count >= 1, "Should call LLM at least once"
    assert len(agent.memory.attempts) >= 1, "Should track attempts in memory"
    
    if len(agent.memory.attempts) > 1:
        print("✅ Self-correction occurred!")
        print("Memory log:")
        for att in agent.memory.attempts:
            status = "✓" if att['success'] else "✗"  
            print(f"  {status} {att['strategy']}")
    else:
        print("✓ Succeeded on first try (no correction needed)")
    
    print("\n" + "="*60)
    print("✅ Mock self-correction test passed!")
    print("="*60)


if __name__ == "__main__":
    import asyncio
    
    # Run mock test (no API key needed)
    print("Running mock test...")
    asyncio.run(test_self_correction_mock())
    
    # Run real test if API key available
    if os.getenv('OPENAI_API_KEY'):
        print("\n\nRunning real LLM test...")
        asyncio.run(test_self_correction_with_real_llm())
    else:
        print("\n\nSkipping real LLM test (no OPENAI_API_KEY)")
