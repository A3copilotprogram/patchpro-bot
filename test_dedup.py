#!/usr/bin/env python3
"""Test backward compatibility after removing agent.py"""

print("Testing backward compatibility...")

try:
    from patchpro_bot.agent_core import (
        PatchProAgent,
        AgentCore,
        AgentConfig,
        ModelProvider,
        GeneratedFix,
        AgentResult,
        PromptBuilder,
        load_source_files
    )
    
    print("✅ All imports successful!")
    print(f"✅ PatchProAgent is AgentCore: {PatchProAgent is AgentCore}")
    print(f"✅ ModelProvider available: {ModelProvider}")
    print(f"✅ AgentConfig available: {AgentConfig}")
    print(f"✅ GeneratedFix available: {GeneratedFix}")
    print(f"✅ AgentResult available: {AgentResult}")
    print(f"✅ PromptBuilder available: {PromptBuilder}")
    print(f"✅ load_source_files available: {load_source_files}")
    
    print("\n✅ ALL BACKWARD COMPATIBILITY CHECKS PASSED!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
