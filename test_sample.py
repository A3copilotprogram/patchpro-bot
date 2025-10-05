# Sample Python file with intentional issues for testing PatchPro analyzer
import os, sys  # Multiple imports on one line (E401)
import json
import unused_import  # Unused import (F401)

# Global variable with unclear name (N806)
g = "global"

def add_numbers(a, b):
    # Missing return type annotation
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
    # Old-style string formatting
    message = "Hello {}".format(name)  # Should use f-string
    return message

def security_issues():
    password = "hardcoded_password123"  # Hardcoded password
    
    # SQL injection vulnerability
    user_input = "'; DROP TABLE users; --"
    query = "SELECT * FROM users WHERE name = '%s'" % user_input
    
    return password, query

def performance_issues():
    numbers = [1, 2, 3, 4, 5]
    # Inefficient list filtering
    even_numbers = list(filter(lambda x: x % 2 == 0, numbers))
    return even_numbers

class BadClass:
    def __init__(self):
        self.value = None
    
    # Method with too many arguments
    def complex_method(self, a, b, c, d, e, f, g, h):
        return a + b + c + d + e + f + g + h

# Unused variable
unused_variable = "This is not used anywhere"

if __name__ == "__main__":
    # Using eval (security issue)
    code = "print('Hello from eval')"
    eval(code)
    
    # Assert in production code
    assert True, "This should not be in production"# Test path normalization
