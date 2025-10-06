"""Example with SQL injection vulnerability."""
import sqlite3

def get_user(username):
    """Fetch user by username - VULNERABLE!"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # VULNERABLE: String concatenation in SQL query
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    
    return cursor.fetchone()

def get_user_safe(username):
    """Fetch user by username - SAFE."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # SAFE: Parameterized query
    query = "SELECT * FROM users WHERE username = ?"
    cursor.execute(query, (username,))
    
    return cursor.fetchone()
