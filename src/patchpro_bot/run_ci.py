from pathlib import Path
import json, os


def main():
    artifacts = Path(os.environ.get("PP_ARTIFACTS", "artifact"))
    artifacts.mkdir(parents=True, exist_ok=True)
    # Merge analyzer outputs if present (ruff/semgrep JSON)
    findings = []
    for p in Path("artifact/analysis").glob("*.json"):
        try:
            findings += json.loads(p.read_text())
        except Exception:
            pass
    summary = f"PatchPro suggestions: {len(findings)} finding(s)"
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
    (artifacts / "patch_001.diff").write_text(diff)
    (artifacts / "report.md").write_text(f"### {summary}\n\n```diff\n{diff}\n```\n")


if __name__ == "__main__":
    main()
