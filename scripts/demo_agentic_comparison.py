#!/usr/bin/env python3
"""
Demo: PatchPro Agentic System vs Baseline

This script demonstrates the agentic system's autonomous behavior,
self-correction, and improved success rates compared to baseline.

Compares 3 modes:
1. Legacy (simple code fixes)
2. Unified Diff (Issue #13 approach)  
3. Agentic V2 (autonomous with self-correction)
"""

import asyncio
import os
import json
import sys
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from patchpro_bot.agent_core import AgentCore, AgentConfig
from patchpro_bot.llm import LLMClient


async def run_comparison_test(findings_count: int = 10):
    """Run comparison between modes."""
    
    print("=" * 80)
    print("PatchPro Agentic System Demo")
    print("=" * 80)
    print()
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not set")
        print("Set it with: export OPENAI_API_KEY='your-key'")
        return
    
    # Test configuration
    test_repo = Path("/opt/andela/genai/patchpro-bot-test-bafecd1")
    findings_file = test_repo / ".patchpro" / "findings.json"
    
    if not findings_file.exists():
        print(f"❌ Error: Test findings not found at {findings_file}")
        return
    
    print(f"📊 Test Setup:")
    print(f"  - Repository: {test_repo}")
    print(f"  - Findings: {findings_count}")
    print(f"  - Model: gpt-4o-mini")
    print()
    
    # Load findings
    with open(findings_file) as f:
        data = json.load(f)
    
    test_findings = data['findings'][:findings_count]
    print(f"✓ Loaded {len(test_findings)} findings for testing\n")
    
    # Save findings to artifact directory for agent to load
    artifact_dir = test_repo / "artifact" / "analysis"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # Create separate files for ruff and semgrep findings
    # Group findings by tool
    ruff_findings = [f for f in test_findings if f.get('source_tool') == 'ruff']
    semgrep_findings = [f for f in test_findings if f.get('source_tool') == 'semgrep']
    
    # Write ruff findings
    if ruff_findings:
        ruff_file = artifact_dir / "ruff_output.json"
        with open(ruff_file, 'w') as f:
            json.dump(ruff_findings, f, indent=2)
    
    # Write semgrep findings
    if semgrep_findings:
        semgrep_file = artifact_dir / "semgrep_output.json"
        with open(semgrep_file, 'w') as f:
            json.dump({'results': semgrep_findings}, f, indent=2)
    
    print(f"✓ Prepared findings for agent in {artifact_dir}\n")
    
    # Results storage
    results = {}
    
    # Mode 1: Legacy (baseline)
    print("=" * 80)
    print("Mode 1: Legacy (Baseline - code fixes)")
    print("=" * 80)
    print("This is the original approach with no diff validation.")
    print()
    
    config1 = AgentConfig(
        base_dir=test_repo,
        openai_api_key=api_key,
        llm_model="gpt-4o-mini",
        use_unified_diff_generation=False,
        enable_agentic_mode=False,
        max_findings=findings_count
    )
    
    agent1 = AgentCore(config1)
    
    try:
        result1 = await agent1.run()
        results['legacy'] = {
            'patches': result1.get('total_patches', 0),
            'successes': result1.get('successful_patches', 0),
            'failures': result1.get('failed_patches', 0),
        }
        results['legacy']['rate'] = (results['legacy']['successes'] / results['legacy']['patches'] 
                                      if results['legacy']['patches'] > 0 else 0)
        
        print(f"✓ Legacy completed:")
        print(f"  - Patches generated: {results['legacy']['patches']}")
        print(f"  - Successes: {results['legacy']['successes']}")
        print(f"  - Success rate: {results['legacy']['rate']:.1%}")
        
    except Exception as e:
        print(f"✗ Legacy failed: {e}")
        results['legacy'] = {'patches': 0, 'successes': 0, 'failures': findings_count, 'rate': 0}
    
    print()
    
    # Mode 2: Unified Diff (Issue #13)
    print("=" * 80)
    print("Mode 2: Unified Diff (Issue #13 - context-aware)")
    print("=" * 80)
    print("Uses real file context and generates unified diffs directly.")
    print()
    
    config2 = AgentConfig(
        base_dir=test_repo,
        openai_api_key=api_key,
        llm_model="gpt-4o-mini",
        use_unified_diff_generation=True,
        enable_agentic_mode=False,
        max_findings=findings_count
    )
    
    agent2 = AgentCore(config2)
    
    try:
        result2 = await agent2.run()
        results['unified'] = {
            'patches': result2.get('total_patches', 0),
            'successes': result2.get('successful_patches', 0),
            'failures': result2.get('failed_patches', 0),
        }
        results['unified']['rate'] = (results['unified']['successes'] / results['unified']['patches']
                                       if results['unified']['patches'] > 0 else 0)
        
        print(f"✓ Unified Diff completed:")
        print(f"  - Patches generated: {results['unified']['patches']}")
        print(f"  - Successes: {results['unified']['successes']}")
        print(f"  - Success rate: {results['unified']['rate']:.1%}")
        
    except Exception as e:
        print(f"✗ Unified Diff failed: {e}")
        results['unified'] = {'patches': 0, 'successes': 0, 'failures': findings_count, 'rate': 0}
    
    print()
    
    # Mode 3: Agentic V2 (autonomous)
    print("=" * 80)
    print("Mode 3: Agentic V2 (AUTONOMOUS with self-correction)")
    print("=" * 80)
    print("Agent autonomously:")
    print("  - Chooses optimal strategy per finding")
    print("  - Validates generated patches")
    print("  - Self-corrects on failure")
    print("  - Learns from attempts")
    print()
    
    config3 = AgentConfig(
        base_dir=test_repo,
        openai_api_key=api_key,
        llm_model="gpt-4o-mini",
        enable_agentic_mode=True,
        agentic_max_retries=3,
        agentic_enable_planning=False,  # Disable for simpler demo
        max_findings=findings_count
    )
    
    agent3 = AgentCore(config3)
    
    try:
        result3 = await agent3.run()
        results['agentic'] = {
            'patches': result3.get('total_patches', 0),
            'successes': result3.get('successful_patches', 0),
            'failures': result3.get('failed_patches', 0),
        }
        results['agentic']['rate'] = (results['agentic']['successes'] / results['agentic']['patches']
                                       if results['agentic']['patches'] > 0 else 0)
        
        print(f"✓ Agentic V2 completed:")
        print(f"  - Patches generated: {results['agentic']['patches']}")
        print(f"  - Successes: {results['agentic']['successes']}")
        print(f"  - Success rate: {results['agentic']['rate']:.1%}")
        
        # Show agent telemetry if available
        if 'agent_telemetry' in result3:
            telem = result3['agent_telemetry']
            print(f"  - Total attempts: {telem.get('total_attempts', 'N/A')}")
            print(f"  - Self-corrections: {telem.get('total_attempts', 0) - results['agentic']['patches']}")
        
    except Exception as e:
        print(f"✗ Agentic V2 failed: {e}")
        results['agentic'] = {'patches': 0, 'successes': 0, 'failures': findings_count, 'rate': 0}
    
    print()
    
    # Final comparison
    print("=" * 80)
    print("FINAL COMPARISON")
    print("=" * 80)
    print()
    
    print(f"{'Mode':<20} {'Patches':<10} {'Success':<10} {'Rate':<10} {'Improvement':<15}")
    print("-" * 80)
    
    baseline_rate = results['legacy']['rate']
    
    for mode_name, mode_label in [('legacy', 'Legacy'), ('unified', 'Unified Diff'), ('agentic', 'Agentic V2')]:
        mode_data = results[mode_name]
        rate = mode_data['rate']
        improvement = ((rate - baseline_rate) / baseline_rate * 100) if baseline_rate > 0 else 0
        
        print(f"{mode_label:<20} {mode_data['patches']:<10} {mode_data['successes']:<10} "
              f"{rate:<10.1%} {improvement:>+7.1f}%")
    
    print()
    print("=" * 80)
    print("Key Findings:")
    print("=" * 80)
    
    if results['agentic']['rate'] > results['unified']['rate']:
        improvement = ((results['agentic']['rate'] - results['unified']['rate']) / 
                      results['unified']['rate'] * 100) if results['unified']['rate'] > 0 else 0
        print(f"✅ Agentic V2 improved success rate by {improvement:.1f}% over Unified Diff")
    
    if results['agentic']['rate'] > results['legacy']['rate']:
        improvement = ((results['agentic']['rate'] - results['legacy']['rate']) / 
                      results['legacy']['rate'] * 100) if results['legacy']['rate'] > 0 else 0
        print(f"✅ Agentic V2 improved success rate by {improvement:.1f}% over Legacy")
    
    print()
    print("Agentic properties demonstrated:")
    print("  ✅ Autonomous decision-making (strategy selection)")
    print("  ✅ Self-correction loops (retry on failure)")  
    print("  ✅ Tool selection (single vs batch)")
    print("  ✅ Goal-oriented behavior (valid patches)")
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Demo PatchPro agentic system")
    parser.add_argument("--findings", type=int, default=10, help="Number of findings to test (default: 10)")
    
    args = parser.parse_args()
    
    asyncio.run(run_comparison_test(findings_count=args.findings))
