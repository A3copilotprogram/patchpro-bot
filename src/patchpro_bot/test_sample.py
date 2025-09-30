
"""
PatchPro: End-to-End Test Sample

This file is used for local and CI testing of PatchPro Bot. It intentionally includes code quality, security, and style issues for the analyzer and patch pipeline.

Example usage for local test:
    python src/patchpro_bot/agent_core.py
    # or run pytest to validate fixes

See README.md for full instructions.
"""

import os, sys  # Multiple imports on one line (E401)
import json

g = "global"

def add_numbers(a, b):
    result = a + b
    print(result)  # Should use logging (T201)
    return result

def bad_exception_handling():
    try:
        result = 1 / 0
    except:  # Bare except clause (E722)
        pass
    
def string_formatting_issues():
    name = "world"
    message = "Hello {}".format(name)  # Should use f-string
    return message

def security_issues():
    password = "hardcoded_password123"  # Hardcoded password
    user_input = "'; DROP TABLE users; --"
    query = "SELECT * FROM users WHERE name = '%s'" % user_input
    return password, query

def performance_issues():
    numbers = [1, 2, 3, 4, 5]
    even_numbers = list(filter(lambda x: x % 2 == 0, numbers))
    return even_numbers

class BadClass:
    def __init__(self):
        self.value = None
    def complex_method(self, a, b, c, d, e, f, g, h):
        return a + b + c + d + e + f + g + h

unused_variable = "This is not used anywhere"

def test_add_numbers():
    assert add_numbers(2, 3) == 5

# PatchPro: End-to-End Test Sample

This file is used for local and CI testing of PatchPro Bot. It intentionally includes code quality, security, and style issues for the analyzer and patch pipeline.

# Example usage for local test:
#   python src/patchpro_bot/agent_core.py
#   # or run pytest to validate fixes

# See README.md for full instructions.
