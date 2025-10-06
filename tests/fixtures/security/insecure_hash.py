"""Example with insecure hash algorithm."""
import hashlib

def hash_password_insecure(password):
    """Hash password using SHA-1 - INSECURE!"""
    # VULNERABLE: SHA-1 is cryptographically broken
    return hashlib.sha1(password.encode()).hexdigest()

def hash_password_secure(password):
    """Hash password using SHA-256 - SECURE."""
    # SECURE: SHA-256 is cryptographically strong
    return hashlib.sha256(password.encode()).hexdigest()

def hash_password_best(password):
    """Hash password using bcrypt - BEST."""
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())
