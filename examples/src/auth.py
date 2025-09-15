"""
Authentication module with security issues.
"""

import hashlib
import hmac


class AuthenticateUser:
    def __init__(self):
        # This is a security issue - hardcoded password
        password = "secret123"
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def login(self, username, provided_password):
        """Login method."""
        password_hash = hashlib.sha256(provided_password.encode()).hexdigest()
        return password_hash == self.password_hash
    
    def validate_token(self, token):
        """Validate authentication token."""
        return hmac.compare_digest(token, "expected_token")
