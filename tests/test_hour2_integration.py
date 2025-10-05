#!/usr/bin/env python3
"""
Integration test for Hour 2: Test with 50 findings using new unified diff approach.

Tests the complete flow:
1. Load 50 findings from test dataset
2. Use AgentCore with new unified diff generation
3. Generate patches using LLM
4. Validate patches with git apply --check
5. Report success rate (target: >80%)
"""

import sys
import json
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from patchpro_bot.agent_core import AgentCore, AgentConfig
from patchpro_bot.models import AnalysisFinding, CodeLocation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_findings(findings_file: str, limit: int = 50):
    """Load findings from JSON file."""
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
            tool=item.get('source_tool', 'unknown'),  # Use source_tool field
        )
        findings.append(finding)
    
    return findings


def write_findings_to_analysis_dir(findings: list, analysis_dir: Path):
    """Write findings to analysis directory for AgentCore."""
    analysis_dir.mkdir(parents=True, exist_ok=True)
    
    # Group findings by tool
    ruff_findings = [f for f in findings if f.tool == 'ruff']
    semgrep_findings = [f for f in findings if f.tool == 'semgrep']
    
    logger.info(f"Grouping: {len(ruff_findings)} Ruff, {len(semgrep_findings)} Semgrep")
    
    # Write Ruff findings in expected format
    if ruff_findings:
        ruff_data = []
        for f in ruff_findings:
            ruff_data.append({
                'code': f.rule_id,
                'message': f.message,
                'filename': f.location.file,
                'location': {
                    'row': f.location.line,
                    'column': f.location.column,
                },
                'end_location': {
                    'row': f.location.end_line or f.location.line,
                    'column': f.location.end_column or f.location.column,
                } if f.location.end_line else None,
                'fix': None,  # Ruff format doesn't always have fix
            })
        
        ruff_file = analysis_dir / "ruff.json"
        with open(ruff_file, 'w') as f:
            json.dump(ruff_data, f, indent=2)
        logger.info(f"Wrote {len(ruff_findings)} Ruff findings to {ruff_file}")
    
    # Write Semgrep findings in expected format
    if semgrep_findings:
        semgrep_data = {
            'results': []
        }
        for f in semgrep_findings:
            semgrep_data['results'].append({
                'check_id': f.rule_id,
                'path': f.location.file,
                'start': {
                    'line': f.location.line,
                    'col': f.location.column,
                },
                'end': {
                    'line': f.location.end_line or f.location.line,
                    'col': f.location.end_column or f.location.column,
                },
                'extra': {
                    'message': f.message,
                    'severity': f.severity.upper(),
                    'metadata': {
                        'category': f.category,
                    },
                },
            })
        
        semgrep_file = analysis_dir / "semgrep.json"
        with open(semgrep_file, 'w') as f:
            json.dump(semgrep_data, f, indent=2)
        logger.info(f"Wrote {len(semgrep_findings)} Semgrep findings to {semgrep_file}")


async def test_integration_with_50_findings():
    """Run integration test with 50 findings."""
    logger.info("=" * 60)
    logger.info("HOUR 2 INTEGRATION TEST: 50 Findings")
    logger.info("=" * 60)
    
    # Setup paths
    repo_path = Path("/opt/andela/genai/patchpro-bot-test-bafecd1")
    findings_file = repo_path / ".patchpro" / "findings.json"
    test_artifact_dir = repo_path / "artifact" / "test"
    test_analysis_dir = test_artifact_dir / "analysis"
    
    logger.info(f"Repo: {repo_path}")
    logger.info(f"Findings: {findings_file}")
    logger.info(f"Test artifact dir: {test_artifact_dir}")
    
    # Load 50 findings
    logger.info("\nLoading 50 findings...")
    findings = load_findings(str(findings_file), limit=50)
    logger.info(f"Loaded {len(findings)} findings")
    
    # Group by file to show distribution
    files_affected = {}
    for f in findings:
        file_path = f.location.file
        if file_path not in files_affected:
            files_affected[file_path] = 0
        files_affected[file_path] += 1
    
    logger.info(f"\nFindings distribution across {len(files_affected)} files:")
    for file_path, count in sorted(files_affected.items(), key=lambda x: x[1], reverse=True)[:10]:
        logger.info(f"  {count:2d} findings in {file_path}")
    
    # Write findings to analysis directory
    write_findings_to_analysis_dir(findings, test_analysis_dir)
    
    # Configure agent with new unified diff approach
    config = AgentConfig(
        base_dir=repo_path,
        analysis_dir=test_analysis_dir,
        artifact_dir=test_artifact_dir,
        use_unified_diff_generation=True,  # Enable new approach
        llm_model="gpt-4o",  # OPTION C: Use smarter model
        max_findings=50,
        max_findings_per_batch=10,  # SMALLER batches for better LLM results
        max_tokens=4096,
        temperature=0.1,
        combine_patches=True,
        generate_summary=True,
    )
    
    logger.info("\n" + "=" * 60)
    logger.info("Running AgentCore with NEW unified diff generation")
    logger.info("=" * 60)
    
    # Run agent
    agent = AgentCore(config)
    
    try:
        results = await agent.run()
        
        logger.info("\n" + "=" * 60)
        logger.info("INTEGRATION TEST RESULTS")
        logger.info("=" * 60)
        
        logger.info(f"\nStatus: {results.get('status')}")
        logger.info(f"Findings processed: {results.get('findings_count')}")
        logger.info(f"Batches processed: {results.get('batches_processed')}")
        logger.info(f"Fixes generated: {results.get('fixes_generated')}")
        logger.info(f"Patches written: {results.get('patches_written')}")
        logger.info(f"Processing time: {results.get('processing_time_seconds', 0):.1f}s")
        
        if results.get('patch_paths'):
            logger.info(f"\nGenerated patches:")
            for path in results['patch_paths']:
                logger.info(f"  - {path}")
        
        # Calculate success rate
        fixes_generated = results.get('fixes_generated', 0)
        findings_count = results.get('findings_count', 0)
        
        if findings_count > 0:
            success_rate = (fixes_generated / findings_count) * 100
            logger.info(f"\n{'='*60}")
            logger.info(f"Success Rate: {success_rate:.1f}% ({fixes_generated}/{findings_count})")
            logger.info(f"Target: >80% (>40/50)")
            
            if success_rate >= 80:
                logger.info("✓ SUCCESS: Exceeded 80% target!")
                return 0
            elif success_rate >= 50:
                logger.warning("⚠ PARTIAL: 50-80% success rate")
                return 1
            else:
                logger.error("✗ FAIL: Below 50% success rate")
                return 2
        else:
            logger.error("✗ FAIL: No findings processed")
            return 2
            
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return 3


async def main():
    """Main entry point."""
    return await test_integration_with_50_findings()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
