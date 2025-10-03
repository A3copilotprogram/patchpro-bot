#!/usr/bin/env python3
"""Simple test to verify agent module works."""

if __name__ == "__main__":
    try:
        from patchpro_bot import agent
        print("✅ Agent module imported successfully!")
        print(f"  - AgentConfig: {agent.AgentConfig}")
        print(f"  - PatchProAgent: {agent.PatchProAgent}")
        print(f"  - ModelProvider: {agent.ModelProvider}")
        print("\n✅ All agent components available!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
