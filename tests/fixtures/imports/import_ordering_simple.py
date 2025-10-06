"""Example with simple import ordering issue."""
import json
import os
import sys  # I001: Import block is not sorted

def main():
    """Main function."""
    print(f"Platform: {sys.platform}")
    print(f"CWD: {os.getcwd()}")
    data = json.dumps({"status": "ok"})
    return data
