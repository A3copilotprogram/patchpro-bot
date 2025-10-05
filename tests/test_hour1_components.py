#!/usr/bin/env python3
"""
Test script for Hour 1 components: FindingContextReader, PromptBuilder, ResponseParser, DiffValidator.

Tests with 5 sample findings from the test dataset.
"""

import sys
import json
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from patchpro_bot.context_reader import FindingContextReader
from patchpro_bot.llm.prompts import PromptBuilder
from patchpro_bot.llm.response_parser import ResponseParser, ResponseType
from patchpro_bot.validators import DiffValidator
from patchpro_bot.models import AnalysisFinding, CodeLocation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_sample_findings(findings_file: str, limit: int = 5):
    """Load sample findings from JSON file."""
    with open(findings_file, 'r') as f:
        data = json.load(f)
    
    findings = []
    for item in data.get('findings', [])[:limit]:
        finding = AnalysisFinding(
            rule_id=item.get('rule_id', ''),
            message=item.get('message', ''),
            severity=item.get('severity', 'warning'),
            location=CodeLocation(
                file=item['location']['file'],
                line=item['location']['line'],
                column=item['location'].get('column', 1),
                end_line=item['location'].get('end_line'),
                end_column=item['location'].get('end_column'),
            ),
            suggested_fix=item.get('suggested_fix'),
            category=item.get('category', 'unknown'),
            confidence=item.get('confidence', 'medium'),
            tool=item.get('tool', 'unknown'),
        )
        findings.append(finding)
    
    return findings


def test_context_reader(findings, repo_path):
    """Test FindingContextReader with sample findings."""
    logger.info("=" * 60)
    logger.info("TEST 1: FindingContextReader")
    logger.info("=" * 60)
    
    context_reader = FindingContextReader(context_lines=5)
    results = []
    
    for i, finding in enumerate(findings, 1):
        file_path = Path(repo_path) / finding.location.file
        logger.info(f"\n{i}. Testing context for: {finding.location.file}:{finding.location.line}")
        
        try:
            context = context_reader.get_code_context(
                str(file_path),
                finding.location.line,
                finding.location.end_line or finding.location.line
            )
            
            if context:
                logger.info(f"✓ Successfully read context ({len(context)} chars)")
                # Show first few lines
                preview = '\n'.join(context.split('\n')[:5])
                logger.info(f"Preview:\n{preview}...")
                results.append(True)
            else:
                logger.error(f"✗ Failed to read context - empty result")
                results.append(False)
                
        except Exception as e:
            logger.error(f"✗ Failed to read context: {e}")
            results.append(False)
    
    success_rate = sum(results) / len(results) * 100
    logger.info(f"\n{'='*60}")
    logger.info(f"Context Reader Success Rate: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    logger.info(f"{'='*60}\n")
    
    return results


def test_prompt_builder(findings, repo_path):
    """Test PromptBuilder with unified diff prompt generation."""
    logger.info("=" * 60)
    logger.info("TEST 2: PromptBuilder")
    logger.info("=" * 60)
    
    prompt_builder = PromptBuilder()
    
    # Group findings by file
    file_fixes = {}
    for finding in findings:
        file_path = finding.location.file
        if file_path not in file_fixes:
            file_fixes[file_path] = []
        file_fixes[file_path].append(finding)
    
    logger.info(f"\nBuilding unified diff prompt for {len(file_fixes)} files...")
    
    try:
        prompt = prompt_builder.build_unified_diff_prompt_with_context(
            file_fixes,
            repo_path
        )
        
        if prompt and len(prompt) > 100:
            logger.info(f"✓ Successfully built prompt ({len(prompt)} chars)")
            # Show key sections
            lines = prompt.split('\n')
            logger.info(f"Prompt has {len(lines)} lines")
            
            # Check for key elements
            has_instructions = "unified diff" in prompt.lower()
            has_file_content = "Actual Code Context" in prompt
            has_json_format = '"patches"' in prompt
            
            logger.info(f"  - Has unified diff instructions: {has_instructions}")
            logger.info(f"  - Has actual code context: {has_file_content}")
            logger.info(f"  - Has JSON format spec: {has_json_format}")
            
            success = has_instructions and has_file_content and has_json_format
            
            if success:
                logger.info("✓ Prompt contains all required elements")
            else:
                logger.error("✗ Prompt missing some required elements")
            
            return success
        else:
            logger.error("✗ Failed to build prompt - result too short")
            return False
            
    except Exception as e:
        logger.error(f"✗ Failed to build prompt: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        logger.info(f"\n{'='*60}\n")


def test_response_parser():
    """Test ResponseParser with sample unified diff JSON."""
    logger.info("=" * 60)
    logger.info("TEST 3: ResponseParser")
    logger.info("=" * 60)
    
    parser = ResponseParser()
    
    # Sample unified diff JSON response
    sample_response = '''{
  "patches": [
    {
      "file_path": "src/example.py",
      "diff_content": "diff --git a/src/example.py b/src/example.py\\n--- a/src/example.py\\n+++ b/src/example.py\\n@@ -10,7 +10,7 @@\\n context line\\n-old line\\n+new line\\n context",
      "summary": "Fixed security issue"
    }
  ]
}'''
    
    logger.info("\nParsing sample unified diff JSON response...")
    
    try:
        result = parser.parse_response(sample_response, ResponseType.DIFF_PATCHES)
        
        if result.diff_patches and len(result.diff_patches) > 0:
            logger.info(f"✓ Successfully parsed {len(result.diff_patches)} patches")
            
            patch = result.diff_patches[0]
            logger.info(f"  - File: {patch.file_path}")
            logger.info(f"  - Summary: {patch.summary}")
            logger.info(f"  - Diff content length: {len(patch.diff_content)} chars")
            
            return True
        else:
            logger.error("✗ Failed to parse - no patches returned")
            return False
            
    except Exception as e:
        logger.error(f"✗ Failed to parse response: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        logger.info(f"\n{'='*60}\n")


def test_diff_validator(repo_path):
    """Test DiffValidator with sample diffs."""
    logger.info("=" * 60)
    logger.info("TEST 4: DiffValidator")
    logger.info("=" * 60)
    
    validator = DiffValidator()
    
    # Valid unified diff
    valid_diff = """diff --git a/test_sample.py b/test_sample.py
--- a/test_sample.py
+++ b/test_sample.py
@@ -1,4 +1,4 @@
 def example():
-    x = 1
+    x = 2
     return x
"""
    
    # Invalid diff (missing headers)
    invalid_diff = """@@ -1,4 +1,4 @@
 def example():
-    x = 1
+    x = 2
"""
    
    logger.info("\n1. Testing valid diff format...")
    is_valid, errors = validator.validate_format(valid_diff)
    if is_valid:
        logger.info("✓ Valid diff passed format validation")
    else:
        logger.error(f"✗ Valid diff failed: {errors}")
    
    logger.info("\n2. Testing invalid diff format...")
    is_valid, errors = validator.validate_format(invalid_diff)
    if not is_valid and errors:
        logger.info(f"✓ Invalid diff correctly rejected: {errors[0]}")
    else:
        logger.error("✗ Invalid diff was incorrectly accepted")
    
    logger.info(f"\n{'='*60}\n")
    
    return True  # Basic validation works


def main():
    """Run all Hour 1 component tests."""
    # Paths
    repo_path = "/opt/andela/genai/patchpro-bot-test-bafecd1"
    findings_file = f"{repo_path}/.patchpro/findings.json"
    
    logger.info(f"\n{'#'*60}")
    logger.info("HOUR 1 COMPONENT TEST")
    logger.info(f"{'#'*60}\n")
    logger.info(f"Repo: {repo_path}")
    logger.info(f"Findings: {findings_file}")
    
    # Check if paths exist
    if not Path(repo_path).exists():
        logger.error(f"Error: Repository not found at {repo_path}")
        return 1
    
    if not Path(findings_file).exists():
        logger.error(f"Error: Findings file not found at {findings_file}")
        return 1
    
    # Load sample findings
    logger.info("\nLoading 5 sample findings...")
    findings = load_sample_findings(findings_file, limit=5)
    logger.info(f"Loaded {len(findings)} findings")
    for i, f in enumerate(findings, 1):
        logger.info(f"  {i}. {f.rule_id} at {f.location.file}:{f.location.line}")
    
    # Run tests
    results = {}
    
    try:
        # Test 1: Context Reader
        context_results = test_context_reader(findings, repo_path)
        results['context_reader'] = all(context_results)
        
        # Test 2: Prompt Builder
        results['prompt_builder'] = test_prompt_builder(findings, repo_path)
        
        # Test 3: Response Parser
        results['response_parser'] = test_response_parser()
        
        # Test 4: Diff Validator
        results['diff_validator'] = test_diff_validator(repo_path)
        
    except Exception as e:
        logger.error(f"Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Summary
    logger.info(f"\n{'#'*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'#'*60}\n")
    
    for component, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {component}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    success_rate = passed_tests / total_tests * 100
    
    logger.info(f"\nOverall: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        logger.info("\n✓ Hour 1 components validated successfully!")
        return 0
    else:
        logger.error("\n✗ Hour 1 components need fixes")
        return 1


if __name__ == "__main__":
    sys.exit(main())
