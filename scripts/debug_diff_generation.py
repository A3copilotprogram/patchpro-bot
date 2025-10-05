#!/usr/bin/env python3
"""Debug script to see what diffs the LLM is generating."""

import sys
import json
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from patchpro_bot.llm.prompts import PromptBuilder
from patchpro_bot.llm.client import LLMClient
from patchpro_bot.llm.response_parser import ResponseParser, ResponseType
from patchpro_bot.models import AnalysisFinding, CodeLocation
from patchpro_bot.validators import DiffValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def debug_single_diff():
    """Generate and inspect a single diff."""
    
    # Create a simple test finding
    finding = AnalysisFinding(
        rule_id="I001",
        message="Import block is un-sorted",
        severity="info",
        location=CodeLocation(
            file="/opt/andela/genai/patchpro-bot-test-bafecd1/src/patchpro_bot/__init__.py",
            line=3,
            column=1,
            end_line=9,
            end_column=25
        ),
        suggested_fix=None,
        category="import",
        confidence="high",
        tool="ruff"
    )
    
    # Build prompt
    prompt_builder = PromptBuilder()
    repo_path = "/opt/andela/genai/patchpro-bot-test-bafecd1"
    file_fixes = {"src/patchpro_bot/__init__.py": [finding]}
    
    prompt = prompt_builder.build_unified_diff_prompt_with_context(file_fixes, repo_path)
    
    logger.info(f"Prompt length: {len(prompt)} chars")
    
    # Get LLM response
    llm_client = LLMClient(model="gpt-4o-mini")
    system_prompt = prompt_builder.get_system_prompt()
    
    response = await llm_client.generate_suggestions(prompt, system_prompt)
    
    logger.info(f"\nLLM Response ({len(response.content)} chars):")
    logger.info("=" * 60)
    
    # Parse response
    parser = ResponseParser()
    parsed = parser.parse_response(response.content, ResponseType.DIFF_PATCHES)
    
    if parsed.diff_patches:
        patch = parsed.diff_patches[0]
        logger.info(f"\nFile: {patch.file_path}")
        logger.info(f"Summary: {patch.summary}")
        logger.info(f"\nDiff Content ({len(patch.diff_content)} chars):")
        logger.info("=" * 60)
        print(patch.diff_content)
        logger.info("=" * 60)
        
        # Validate
        validator = DiffValidator()
        
        # Normalize paths
        normalized = validator.normalize_diff_paths(patch.diff_content, repo_path)
        if normalized != patch.diff_content:
            logger.info("\nPath normalization changed the diff")
            patch.diff_content = normalized
        
        # Validate format
        is_valid, errors = validator.validate_format(patch.diff_content)
        logger.info(f"\nFormat validation: {'✓ PASS' if is_valid else '✗ FAIL'}")
        if errors:
            for err in errors:
                logger.error(f"  - {err}")
        
        # Validate applicability
        can_apply, apply_error = validator.can_apply(patch.diff_content, repo_path)
        logger.info(f"Git apply validation: {'✓ PASS' if can_apply else '✗ FAIL'}")
        if not can_apply:
            logger.error(f"  Error: {apply_error}")
            
            # Save to file for manual inspection
            debug_file = Path("/tmp/debug_patch.diff")
            debug_file.write_text(patch.diff_content)
            logger.info(f"\nSaved patch to {debug_file} for inspection")
            logger.info(f"Try: cd {repo_path} && git apply --check {debug_file}")
    else:
        logger.error("No patches generated")


if __name__ == "__main__":
    asyncio.run(debug_single_diff())
