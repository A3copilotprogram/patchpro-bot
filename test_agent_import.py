#!/usr/bin/env python3
"""Simple test to verify agent module works."""

if __name__ == "__main__":
    try:
        from patchpro_bot import agent_core
        print("✅ Agent core module imported successfully!")
        print(f"  - AgentConfig: {agent_core.AgentConfig}")
        print(f"  - AgentCore: {agent_core.AgentCore}")
        print(f"  - PatchProAgent (alias): {agent_core.PatchProAgent}")
        print(f"  - ModelProvider: {agent_core.ModelProvider}")
        print("\n✅ All agent components available!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
