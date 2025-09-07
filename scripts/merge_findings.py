import json
import sys
def load_json(file_path: str) -> dict | list:
    """Load JSON from file with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {file_path}: {e}")
        return {}

def normalize_ruff_findings(ruff_data: dict) -> list:
    """Normalize Ruff findings to common schema."""
    findings = []
    if isinstance(ruff_data, list):
        for item in ruff_data:
            findings.append({
                'tool': 'ruff',
                'file': item.get('filename', ''),
                'line': item.get('location', {}).get('row', 0),
                'code': item.get('code', ''),
                'message': item.get('message', ''),
                'severity': 'info'
            })
    return findings

def normalize_semgrep_findings(semgrep_data: dict) -> list:
    """Normalize Semgrep findings to common schema."""
    findings = []
    if isinstance(semgrep_data, dict) and 'results' in semgrep_data:
        for result in semgrep_data['results']:
            findings.append({
                'tool': 'semgrep',
                'file': result.get('path', ''),
                'line': result.get('start', {}).get('line', 0),
                'code': result.get('check_id', ''),
                'message': result.get('extra', {}).get('message', ''),
                'severity': result.get('extra', {}).get('severity', 'info')
            })
    return findings

def main(ruff_path: str, semgrep_path: str, out_path: str):
    """Merge and deduplicate findings."""
    ruff_data = load_json(ruff_path)
    semgrep_data = load_json(semgrep_path)
    
    findings = normalize_ruff_findings(ruff_data) + normalize_semgrep_findings(semgrep_data)
    
    # Deduplicate based on tool, file, line, code
    unique_findings = {(f['tool'], f['file'], f['line'], f['code']): f for f in findings}
    findings = list(unique_findings.values())
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(findings, f, indent=2)
    print(f"Merged {len(findings)} unique findings to {out_path}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage: merge_findings.py <ruff.json> <semgrep.json> <out.json>')
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
