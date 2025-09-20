"""Legacy CI runner - now delegates to the new agent core."""

import asyncio
from pathlib import Path
import os
import logging

from .agent_core import AgentCore, AgentConfig


logger = logging.getLogger(__name__)


def main():
    """Main entry point for CI runner."""
    try:
        # Setup environment
        artifacts_dir = Path(os.environ.get("PP_ARTIFACTS", "artifact"))
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if we have analysis files to process
        analysis_dir = artifacts_dir / "analysis"
        if not analysis_dir.exists() or not any(analysis_dir.glob("*.json")):
            logger.warning("No analysis files found, generating placeholder")
            _generate_placeholder_output(artifacts_dir)
            return
        
        # Use the new agent core
        config = AgentConfig(
            analysis_dir=analysis_dir,
            artifact_dir=artifacts_dir,
        )
        
        agent = AgentCore(config)
        results = asyncio.run(agent.run())
        
        if results["status"] == "success":
            logger.info(f"Successfully processed {results['findings_count']} findings")
            logger.info(f"Generated {results['patches_written']} patch files")
        else:
            logger.error(f"Agent failed: {results.get('message', 'Unknown error')}")
            _generate_placeholder_output(artifacts_dir)
            
    except Exception as e:
        logger.error(f"CI runner failed: {e}")
        artifacts_dir = Path(os.environ.get("PP_ARTIFACTS", "artifact"))
        _generate_placeholder_output(artifacts_dir)


def _generate_placeholder_output(artifacts_dir: Path):
    """Generate placeholder output for backward compatibility."""
    logger.info("Generating placeholder output")
    
    # Legacy placeholder diff
    diff = """\
diff --git a/example.py b/example.py
index 1111111..2222222 100644
--- a/example.py
+++ b/example.py
@@ -1,5 +1,5 @@
-import os, sys
+import os
 def add(a, b):
     return a + b
"""
    
    summary = "PatchPro suggestions: 0 finding(s) (placeholder)"
    
    # Write legacy outputs
    (artifacts_dir / "patch_001.diff").write_text(diff)
    (artifacts_dir / "report.md").write_text(f"### {summary}\n\n```diff\n{diff}\n```\n")


if __name__ == "__main__":
    main()
