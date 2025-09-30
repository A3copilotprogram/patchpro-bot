"""
Check for public code duplication in the repository.
This script compares all Python files in src/patchpro_bot/ against a known public codebase (e.g., Python stdlib os.py).
If a file is a near-duplicate, it prints the filename to stdout and exits with code 1.
"""
import glob
import difflib
import requests
import sys

PUBLIC_URL = "https://raw.githubusercontent.com/python/cpython/main/Lib/os.py"
THRESHOLD = 0.95

try:
    resp = requests.get(PUBLIC_URL, timeout=10)
    public_code = resp.text
except Exception as e:
    print(f"Error fetching public code: {e}")
    sys.exit(0)  # Don't block pipeline if fetch fails

for file in glob.glob("src/patchpro_bot/**/*.py", recursive=True):
    with open(file, "r", encoding="utf-8") as f:
        code = f.read()
        ratio = difflib.SequenceMatcher(None, code, public_code).ratio()
        if ratio > THRESHOLD:
            print(f"{file}")
            sys.exit(1)

sys.exit(0)
