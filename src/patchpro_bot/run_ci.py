import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_findings(artifacts_dir: Path) -> list:
    """Load and merge findings from Ruff and Semgrep JSON files."""
    findings = []
    analysis_dir = artifacts_dir / "analysis"
    if not analysis_dir.exists():
        logging.warning("Analysis directory not found.")
        return findings
    
    for json_file in analysis_dir.glob("*.json"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    findings.extend(data)
                elif isinstance(data, dict) and 'results' in data:
                    findings.extend(data['results'])
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"Error loading {json_file}: {e}")
    
    return findings

def generate_report(findings: list, artifacts_dir: Path) -> str:
    """Generate a markdown report and diff file."""
    summary = f"PatchPro suggestions: {len(findings)} finding(s)"
    diff_content = """\
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
    diff_path = artifacts_dir / "patch_001.diff"
    diff_path.write_text(diff_content)
    
    report = f"### {summary}\n\n```diff\n{diff_content}\n```\n"
    (artifacts_dir / "report.md").write_text(report)
    return report

def main():
    """Main entry point for CI execution."""
    artifacts_dir = Path(os.environ.get("PP_ARTIFACTS", "artifact"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    findings = load_findings(artifacts_dir)
    report = generate_report(findings, artifacts_dir)
    logging.info("Report generated successfully.")

def run_ci(input_data: dict) -> str | bool:
    """
    Process static analysis findings and generate feedback.

    Args:
        input_data (dict): Dictionary containing findings.

    Returns:
        str: "Analysis complete" if findings were processed.
        bool: True if no findings.
    """
    if not input_data or not input_data.get("findings"):
        return True
    
    findings = input_data["findings"]
    logging.info(f"Processing {len(findings)} findings.")
    return "Analysis complete"

if __name__ == "__main__":
    main()
