"""Example with multiple imports on one line."""
import os, sys, json  # E401: Multiple imports on one line

def process_data():
    """Process some data using imported modules."""
    data = json.loads('{"key": "value"}')
    print(f"Running on {sys.platform} in {os.getcwd()}")
    return data
