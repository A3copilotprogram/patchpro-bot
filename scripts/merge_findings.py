"""Merge findings from Ruff and Semgrep into a single JSON file."""

import sys
import json
from pathlib import Path

def load_findings(path):
    """Load findings from a JSON file, handling common formats."""
    if not Path(path).is_file():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            # Try to extract findings from common formats
            if isinstance(data, dict) and 'findings' in data:
                return data['findings']
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and 'results' in data:
                return data['results']
            return []
        except (json.JSONDecodeError, OSError):
            return []

def main():
    """Main entry point for merging findings."""
    if len(sys.argv) != 4:
        print(
            "Usage: python merge_findings.py <ruff-findings.json> "
            "<semgrep-findings.json> <output-findings.json>"
        )
        sys.exit(1)
    ruff_path, semgrep_path, output_path = sys.argv[1:4]
    ruff_findings = load_findings(ruff_path)
    semgrep_findings = load_findings(semgrep_path)
    merged = {
        "findings": ruff_findings + semgrep_findings
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2)
    print(
        f"Merged {len(ruff_findings)} Ruff and "
        f"{len(semgrep_findings)} Semgrep findings into {output_path}"
    )

if __name__ == "__main__":
    main()