#!/usr/bin/env python3
"""
Test script for telemetry infrastructure.

Generates a few patches with tracing enabled and shows what's captured.
"""

import asyncio
import os
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from patchpro_bot.agentic_patch_generator_v2 import AgenticPatchGeneratorV2
from patchpro_bot.llm import LLMClient
from patchpro_bot.models import AnalysisFinding
from patchpro_bot.telemetry import PatchTracer


async def test_telemetry():
    """Test telemetry by generating patches with tracing enabled."""
    
    print("=" * 80)
    print("PatchPro Telemetry Test")
    print("=" * 80)
    print()
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not set")
        return
    
    # Load findings
    test_repo = Path("/opt/andela/genai/patchpro-bot-test-bafecd1")
    findings_file = test_repo / ".patchpro" / "findings.json"
    
    if not findings_file.exists():
        print(f"❌ Error: Test findings not found at {findings_file}")
        return
    
    with open(findings_file) as f:
        data = json.load(f)
    
    # Take just 5 findings for quick test
    raw_findings = data['findings'][:5]
    
    # Convert to AnalysisFinding objects
    findings = []
    for f in raw_findings:
        f_copy = f.copy()
        if 'source_tool' in f_copy and 'tool' not in f_copy:
            f_copy['tool'] = f_copy.pop('source_tool')
        findings.append(AnalysisFinding(**f_copy))
    
    print(f"📊 Test Setup:")
    print(f"  - Repository: {test_repo}")
    print(f"  - Findings: {len(findings)}")
    print(f"  - Tracing: ENABLED")
    print()
    
    # Create LLM client
    llm_client = LLMClient(api_key=api_key, model="gpt-4o-mini")
    
    # Create agentic generator WITH TRACING
    print("🤖 Initializing Agentic Patch Generator V2 with tracing...")
    generator = AgenticPatchGeneratorV2(
        llm_client=llm_client,
        repo_path=test_repo,
        max_retries=3,
        enable_planning=False,
        enable_tracing=True  # ← ENABLE TELEMETRY
    )
    print(f"   - Traces will be saved to: {test_repo}/.patchpro/traces/")
    print()
    
    # Generate patches
    print("=" * 80)
    print("🚀 Running Patch Generation with Tracing...")
    print("=" * 80)
    print()
    
    try:
        result = await generator.generate_patches(findings)
        
        print()
        print("=" * 80)
        print("✅ PATCHES GENERATED")
        print("=" * 80)
        print()
        
        patches = result.get('patches', [])
        print(f"Total patches generated: {len(patches)}")
        print(f"Success rate: {result.get('success_rate', 0):.1%}")
        print()
        
        # Now check traces
        print("=" * 80)
        print("📊 TELEMETRY ANALYSIS")
        print("=" * 80)
        print()
        
        # Get summary stats
        tracer = generator.tracer
        stats = tracer.get_summary_stats()
        
        print("Summary Statistics:")
        print(f"  - Total traces: {stats['total_traces']}")
        print(f"  - Successful traces: {stats['successful_traces']}")
        print(f"  - Success rate: {stats['success_rate']:.1%}")
        print(f"  - Average cost: ${stats['avg_cost_usd']:.4f}")
        print(f"  - Average latency: {stats['avg_latency_ms']:.0f}ms")
        print()
        
        print("Cost by Strategy:")
        for strategy, cost in stats['cost_by_strategy'].items():
            print(f"  - {strategy}: ${cost:.4f}")
        print()
        
        if stats['top_failures']:
            print("Top Failures:")
            for failure in stats['top_failures']:
                print(f"  - {failure['rule_id']}: {failure['count']} failures")
            print()
        
        # Show a few traces
        print("Sample Traces:")
        traces = tracer.query_traces(limit=3)
        for i, trace in enumerate(traces, 1):
            print(f"\nTrace {i}:")
            print(f"  - Rule: {trace['rule_id']}")
            print(f"  - File: {trace['file_path']}")
            print(f"  - Strategy: {trace['strategy']}")
            print(f"  - Status: {trace['final_status']}")
            print(f"  - Tokens: {trace['tokens_used']}")
            print(f"  - Cost: ${trace['cost_usd']:.4f}")
            print(f"  - Latency: {trace['latency_ms']}ms")
            print(f"  - Validation: {'✅ PASSED' if trace['validation_passed'] else '❌ FAILED'}")
        
        print()
        print("=" * 80)
        print("📁 Trace Files Location")
        print("=" * 80)
        print()
        print(f"SQLite database: {test_repo}/.patchpro/traces/traces.db")
        print(f"JSON traces: {test_repo}/.patchpro/traces/*.json")
        print()
        print("You can:")
        print("  - Query SQLite with: sqlite3 .patchpro/traces/traces.db")
        print("  - View JSON with: cat .patchpro/traces/<trace_id>.json | jq")
        print("  - Build UI with: Streamlit app (coming in Week 2)")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_telemetry())
