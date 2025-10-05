"""
Test AgenticPatchGeneratorV2 with real working APIs.

This tests the agentic system built on PROVEN components from Issue #13.
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from patchpro_bot.agentic_patch_generator_v2 import AgenticPatchGeneratorV2
from patchpro_bot.models import AnalysisFinding, CodeLocation, Severity
from patchpro_bot.llm import LLMClient


# Test data
TEST_FINDINGS_PATH = Path("/opt/andela/genai/patchpro-bot-test-bafecd1/.patchpro/findings.json")
TEST_REPO_PATH = Path("/opt/andela/genai/patchpro-bot-test-bafecd1")


def load_test_findings(count=5):
    """Load real findings from test worktree."""
    with open(TEST_FINDINGS_PATH) as f:
        data = json.load(f)
    
    findings = []
    for f_data in data['findings'][:count]:
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
async def test_v2_with_mock():
    """Test V2 agentic system with mock LLM."""
    
    print("\n" + "="*60)
    print("Testing AgenticPatchGeneratorV2 (Built on Issue #13)")
    print("="*60 + "\n")
    
    findings = load_test_findings(count=2)
    print(f"Loaded {len(findings)} test findings\n")
    
    # Mock LLM that returns valid unified diff
    mock_llm = AsyncMock()
    mock_llm.generate_async.return_value = Mock(
        content="""{
  "patches": [
    {
      "file_path": "test.py",
      "diff_content": "--- a/test.py\\n+++ b/test.py\\n@@ -1,3 +1,3 @@\\n import os\\n-import sys\\n+# import sys removed\\n print('test')",
      "summary": "Remove unused import"
    }
  ]
}"""
    )
    
    # Create V2 agent
    agent = AgenticPatchGeneratorV2(
        llm_client=mock_llm,
        repo_path=TEST_REPO_PATH,
        max_retries=3,
        enable_planning=False
    )
    
    print("V2 Agent initialized:")
    print(f"  - Tools: {list(agent.tool_registry.tools.keys())}")
    print(f"  - Max retries: {agent.max_retries}\n")
    
    # Test tools individually first
    print("Test 1: Analyze finding...")
    analysis = agent._analyze_finding_complexity(findings[0])
    assert analysis['success'], "Analysis should succeed"
    print(f"  ✓ Complexity: {analysis['result']['complexity']}")
    print()
    
    # Test single patch generation
    print("Test 2: Generate single patch...")
    result = await agent._generate_single_patch(findings[0])
    
    if result['success']:
        patches = result['result']['patches']
        print(f"  ✓ Generated {len(patches)} patch(es)")
        for patch in patches:
            print(f"    - {patch.file_path}")
    else:
        print(f"  ✗ Failed: {result.get('error')}")
    
    print()
    
    # Test full generation with self-correction
    print("Test 3: Full generation with agentic behavior...")
    result = await agent.generate_patches(findings)
    
    print(f"\nResults:")
    print(f"  - Total findings: {result['total_findings']}")
    print(f"  - Patches generated: {len(result['patches'])}")
    print(f"  - Success rate: {result['success_rate']:.1%}")
    print(f"  - Total attempts: {result['total_attempts']}")
    print()
    
    if result['memory']['attempts']:
        print("Memory:")
        print(f"  - Attempts: {result['memory']['attempts']}")
        print(f"  - Successful strategies: {result['memory']['successful_strategies']}")
        print(f"  - Failed strategies: {result['memory']['failed_strategies']}")
    
    print("\n" + "="*60)
    print("✅ V2 Agent test completed!")
    print("="*60)


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv('OPENAI_API_KEY'), reason="No API key")
async def test_v2_with_real_llm():
    """Test V2 with real LLM (requires API key)."""
    
    print("\n" + "="*60)
    print("Testing V2 with REAL LLM")
    print("="*60 + "\n")
    
    findings = load_test_findings(count=3)
    print(f"Testing with {len(findings)} real findings:")
    for f in findings:
        print(f"  - {f.rule_id} at {f.location.file}:{f.location.line}")
    print()
    
    # Create real LLM client
    llm_client = LLMClient(
        api_key=os.getenv('OPENAI_API_KEY'),
        model="gpt-4o-mini"
    )
    
    agent = AgenticPatchGeneratorV2(
        llm_client=llm_client,
        repo_path=TEST_REPO_PATH,
        max_retries=3,
        enable_planning=False
    )
    
    print("Calling agent.generate_patches() with REAL LLM...")
    print("(This will make actual API calls)\n")
    
    result = await agent.generate_patches(findings)
    
    print(f"\n{'='*60}")
    print("REAL LLM Results:")
    print(f"{'='*60}")
    print(f"Total findings: {result['total_findings']}")
    print(f"Patches generated: {len(result['patches'])}")
    print(f"Success rate: {result['success_rate']:.1%}")
    print(f"Total attempts: {result['total_attempts']}")
    print()
    
    if result['patches']:
        print("Generated patches:")
        for i, patch in enumerate(result['patches'], 1):
            print(f"  {i}. {patch.file_path}")
            print(f"     Summary: {patch.summary}")
    
    print()
    print("Memory telemetry:")
    print(f"  - Attempts made: {result['memory']['attempts']}")
    print(f"  - Successful strategies: {result['memory']['successful_strategies']}")
    print(f"  - Failed strategies: {result['memory']['failed_strategies']}")
    
    # Validate at least some success
    assert result['success_rate'] > 0, "Should have at least some successful patches"
    
    print("\n✅ Real LLM test passed!")


if __name__ == "__main__":
    import asyncio
    
    # Run mock test
    print("Running mock test...")
    asyncio.run(test_v2_with_mock())
    
    # Run real test if API key available
    if os.getenv('OPENAI_API_KEY'):
        print("\n\nRunning REAL LLM test...")
        asyncio.run(test_v2_with_real_llm())
    else:
        print("\n\nSkipping real LLM test (no OPENAI_API_KEY)")
