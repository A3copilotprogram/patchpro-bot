"""Example with unused import."""
import os
import sys  # F401: 'sys' imported but unused
import json

def read_file(path):
    """Read file contents."""
    with open(path) as f:
        return json.load(f)

# Note: sys and os are imported but only json is used
