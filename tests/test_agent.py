#!/usr/bin/env python3
"""
Quick test of the PatchPro agent module.
This verifies the module can be imported and basic functionality works.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from patchpro_bot.agent import (
            PatchProAgent,
            AgentConfig,
            ModelProvider,
            GeneratedFix,
            AgentResult,
            PromptBuilder,
            load_source_files
        )
        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_config():
    """Test AgentConfig creation (without API key)."""
    print("\nTesting AgentConfig...")
    try:
        from patchpro_bot.agent import AgentConfig, ModelProvider
        
        # Test with dummy API key
        config = AgentConfig(
            provider=ModelProvider.OPENAI,
            model="gpt-4o-mini",
            api_key="test-key",
            max_tokens=1000
        )
        
        assert config.model == "gpt-4o-mini"
        assert config.max_tokens == 1000
        assert config.temperature == 0.1
        print("✅ AgentConfig creation successful!")
        return True
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False

def test_prompt_builder():
    """Test PromptBuilder functionality."""
    print("\nTesting PromptBuilder...")
    try:
        from patchpro_bot.agent import PromptBuilder
        from patchpro_bot.analyzer import Finding, Location
        
        # Create a sample finding
        finding = Finding(
            id="test123",
            rule_id="E501",
            rule_name="line-too-long",
            message="Line too long (100 > 88 characters)",
            severity="warning",
            category="style",
            location=Location(
                file="test.py",
                line=10,
                column=1
            ),
            source_tool="ruff"
        )
        
        # Test prompt building
        file_contents = {
            "test.py": "# This is a test\n" * 20
        }
        
        prompt = PromptBuilder.build_fix_prompt([finding], file_contents)
        
        assert "test123" in prompt
        assert "E501" in prompt
        assert len(prompt) > 100
        
        print("✅ PromptBuilder working correctly!")
        return True
    except Exception as e:
        print(f"❌ PromptBuilder test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cli_integration():
    """Test that CLI can import agent module."""
    print("\nTesting CLI integration...")
    try:
        from patchpro_bot.cli import app
        
        # Check that agent command exists
        commands = [cmd.name for cmd in app.registered_commands]
        assert "agent" in commands
        
        print("✅ CLI integration successful!")
        return True
    except Exception as e:
        print(f"❌ CLI integration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("PatchPro Agent Module Tests")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Config", test_config()))
    results.append(("PromptBuilder", test_prompt_builder()))
    results.append(("CLI Integration", test_cli_integration()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Agent module is ready to use.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
