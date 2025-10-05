# Test file with an intentional issue for Ruff
import os
import sys  # Unused import - Ruff will complain

def test_function():
    x=1+2  # No spaces around operators - Ruff will complain
    return x
