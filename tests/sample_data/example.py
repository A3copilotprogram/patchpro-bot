"""Sample Python file with various issues for testing."""

import os, sys  # F401: sys imported but unused
import json

def process_data(data):
    # E501: Line too long (this line intentionally exceeds 79 characters to trigger the rule)
    result = data.upper()   # W291: Trailing whitespace after this comment
    return result

def calculate_sum(a, b):
    return a + b

class DataProcessor:
    def __init__(self):
        self.data = None
        
    def load_file(self, filename):
        # This will trigger Semgrep warning about context manager
        file = open(filename)
        content = file.read()
        file.close()
        return content
