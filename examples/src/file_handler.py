"""
File handling module with best practice issues.
"""

import os


class FileHandler:
    def __init__(self, base_path):
        self.base_path = base_path
    
    def read_file_content(self, filename):
        """Read file content - not using context manager."""
        full_path = os.path.join(self.base_path, filename)
        file = open(filename)
        content = file.read()
        file.close()
        return content
    
    def write_file_content(self, filename, content):
        """Write file content properly."""
        full_path = os.path.join(self.base_path, filename)
        with open(full_path, 'w') as file:
            file.write(content)
    
    def file_exists(self, filename):
        """Check if file exists."""
        full_path = os.path.join(self.base_path, filename)
        return os.path.exists(full_path)
