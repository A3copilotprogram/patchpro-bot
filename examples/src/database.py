"""
Database module with SQL injection vulnerability.
"""

import sqlite3


class Database:
    def __init__(self, db_path):
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
    
    def create_table(self):
        """Create users table."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT NOT NULL
            )
        """)
        self.connection.commit()
    
    def get_user_by_id(self, user_id):
        """Get user by ID - vulnerable to SQL injection."""
        query = f"SELECT * FROM users WHERE id = {user_id}"
        self.cursor.execute(query)
        return self.cursor.fetchone()
    
    def close(self):
        """Close database connection."""
        self.connection.close()
