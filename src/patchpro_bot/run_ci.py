"""Enhanced CI runner with integrated analysis normalization."""

import asyncio
from pathlib import Path
import os
import logging
from dotenv import load_dotenv

from .agent_core import AgentCore, AgentConfig
from .analyzer import FindingsAnalyzer


logger = logging.getLogger(__name__)


def main():
    """Main entry point for CI runner with integrated analysis normalization."""
    # Load environment variables from .env file
    load_dotenv()
    
    try:
        # Setup environment
        artifacts_dir = Path(os.environ.get("PP_ARTIFACTS", "artifact"))
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine base directory - if artifacts is absolute path, use its parent
        # If relative, use current working directory
        if artifacts_dir.is_absolute():
            base_dir = artifacts_dir.parent.absolute()
        else:
            base_dir = Path.cwd().absolute()
        
        logger.info(f"Using base directory: {base_dir}")
        logger.info(f"Using artifacts directory: {artifacts_dir}")
        
        # Check if we have analysis files to process
        analysis_dir = artifacts_dir / "analysis"
        if not analysis_dir.exists() or not any(analysis_dir.glob("*.json")):
            logger.warning("No analysis files found, generating placeholder")
            _generate_placeholder_output(artifacts_dir)
            return
        
        # ENHANCEMENT: Use Denis's analyzer for finding normalization
        try:
            logger.info("Normalizing findings using integrated analyzer...")
            analyzer = FindingsAnalyzer()
            normalized_findings = analyzer.load_and_normalize(str(analysis_dir))
            
            # Save normalized findings for AgentCore to use
            normalized_path = artifacts_dir / "normalized_findings.json"
            normalized_findings.save(str(normalized_path))
            logger.info(f"Saved {len(normalized_findings.findings)} normalized findings")
            
        except Exception as e:
            logger.warning(f"Analyzer normalization failed, falling back to raw processing: {e}")
        
        # Use the agent core (enhanced to prefer normalized findings)
        config = AgentConfig(
            analysis_dir=analysis_dir,
            artifact_dir=artifacts_dir,
            base_dir=base_dir,
        )
        
        agent = AgentCore(config)
        results = asyncio.run(agent.run())
        
        logger.info(f"Agent processing completed: {results}")
        
    except Exception as e:
        logger.error(f"CI runner failed: {e}")
        raise


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