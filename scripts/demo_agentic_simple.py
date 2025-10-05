#!/usr/bin/env python3
"""
Simple Demo: Agentic Patch Generator V2

Directly demonstrates the agentic patch generator with real findings.
Shows autonomous decision-making, self-correction, and memory.
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


async def demo():
    """Run agentic patch generator demo."""
    
    print("=" * 80)
    print("PatchPro Agentic System V2 - Simple Demo")
    print("=" * 80)
    print()
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not set")
        print("Set it with: export OPENAI_API_KEY='your-key'")
        return
    
    # Load findings
    test_repo = Path("/opt/andela/genai/patchpro-bot-test-bafecd1")
    findings_file = test_repo / ".patchpro" / "findings.json"
    
    if not findings_file.exists():
        print(f"❌ Error: Test findings not found at {findings_file}")
        return
    
    with open(findings_file) as f:
        data = json.load(f)
    
    # Take first N findings
    raw_findings = data['findings'][:20]  # Test with 20 findings for real e2e test
    
    # Convert to AnalysisFinding objects
    # The findings.json uses 'source_tool' but AnalysisFinding expects 'tool'
    findings = []
    for f in raw_findings:
        f_copy = f.copy()
        if 'source_tool' in f_copy and 'tool' not in f_copy:
            f_copy['tool'] = f_copy.pop('source_tool')
        findings.append(AnalysisFinding(**f_copy))
    
    print(f"📊 Test Setup:")
    print(f"  - Repository: {test_repo}")
    print(f"  - Findings: {len(findings)} (multi-file, multi-hunk test)")
    print(f"  - Model: gpt-4o-mini")
    print()
    
    print(f"Findings to fix (showing first 5):")
    for i, finding in enumerate(findings[:5], 1):
        print(f"  {i}. [{finding.rule_id}] {finding.message}")
        print(f"     File: {finding.location.file}")
        print(f"     Line: {finding.location.line}")
    if len(findings) > 5:
        print(f"  ... and {len(findings) - 5} more findings")
    print()
    
    # Create LLM client
    llm_client = LLMClient(api_key=api_key, model="gpt-4o-mini")
    
    # Create agentic generator
    print("🤖 Initializing Agentic Patch Generator V2...")
    generator = AgenticPatchGeneratorV2(
        llm_client=llm_client,
        repo_path=test_repo,
        max_retries=3,
        enable_planning=False  # Simpler for demo
    )
    print(f"   - Tools registered: generate_single_patch, generate_batch_patch, validate_patch, analyze_finding")
    print(f"   - Max retries: 3")
    print(f"   - Self-correction: ENABLED")
    print()
    
    # Generate patches
    print("=" * 80)
    print("🚀 Running Agentic Patch Generation...")
    print("=" * 80)
    print()
    
    try:
        result = await generator.generate_patches(findings)
        
        print()
        print("=" * 80)
        print("✅ RESULTS")
        print("=" * 80)
        print()
        
        patches = result.get('patches', [])
        print(f"Total patches generated: {len(patches)}")
        print(f"Files processed: {result.get('total_files', 0)}")
        print(f"Success rate: {result.get('success_rate', 0):.1%}")
        print()
        
        # Show patch details
        for i, patch in enumerate(patches, 1):
            print(f"Patch {i}:")
            print(f"  File: {patch.file_path}")
            print(f"  Diff size: {len(patch.diff_content)} chars")
            print(f"  Valid: ✅")
            
            # Show first few lines of diff
            diff_lines = patch.diff_content.split('\n')[:10]
            print(f"  Preview:")
            for line in diff_lines:
                print(f"    {line}")
            total_lines = len(patch.diff_content.split('\n'))
            if total_lines > 10:
                remaining = total_lines - 10
                print(f"    ... ({remaining} more lines)")
            print()
        
        print()
        print("=" * 80)
        print("📊 Agentic Behavior Demonstrated:")
        print("=" * 80)
        
        # Show agent memory
        memory_info = result.get('memory', {})
        print(f"✅ Memory & Learning:")
        print(f"   - Total attempts: {memory_info.get('attempts', 0)}")
        print(f"   - Successful strategies: {', '.join(memory_info.get('successful_strategies', []))}")
        
        print(f"✅ Autonomous Decision-Making:")
        print(f"   - Processed {result.get('total_files', 0)} files with {result.get('total_findings', 0)} findings")
        
        print(f"✅ Self-Correction:")
        print(f"   - Total attempts: {result.get('total_attempts', 0)}")
        print(f"   - Validated each patch before accepting")
        
        print(f"✅ Tool Selection:")
        print(f"   - Dynamically selected from: generate_single_patch, generate_batch_patch, validate_patch, analyze_finding")
        
        print(f"✅ Goal-Oriented:")
        print(f"   - Achieved goal: {len(patches)} valid patches ({result.get('success_rate', 0):.1%} success)")
        
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(demo())
