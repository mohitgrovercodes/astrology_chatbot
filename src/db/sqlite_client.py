"""
SQLite Client for NakshatraAI
=============================

Handles persistent storage for:
1. User Profiles
2. Conversation History

Schema is automatically created on initialization.
"""

import sqlite3
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

class SQLiteClient:
    """Client for managing SQLite database interactions."""
    
    def __init__(self, db_path: str = "data/astro.db"):
        """
        Initialize database connection and schema.
        
        Args:
            db_path: Path to SQLite database file
        """
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self._init_schema()
        
    def get_connection(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """Create tables if they don't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                birth_date TEXT,
                birth_time TEXT,
                birth_place TEXT,
                latitude REAL,
                longitude REAL,
                timezone TEXT,
                system TEXT DEFAULT 'vedic',
                language TEXT DEFAULT 'hi-lat',
                created_at TEXT,
                last_active TEXT
            )
        """)
        
        # 2. Conversations Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                intent TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        
        conn.commit()
        conn.close()
        print(f"[DB] SQLite schema initialized at {self.db_path}")

    # =========================================================================
    # USER OPERATIONS
    # =========================================================================

    def upsert_user(self, user_data: Dict[str, Any]):
        """
        Insert or Update a user profile.
        
        Args:
            user_data: Dictionary containing user fields matching schema
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Extract fields with defaults
        user_id = user_data.get('user_id')
        if not user_id:
            raise ValueError("user_id is required")
            
        fields = [
            'user_id', 'name', 'email', 
            'birth_date', 'birth_time', 'birth_place', 
            'latitude', 'longitude', 'timezone', 
            'system', 'language', 'created_at', 'last_active'
        ]
        
        # Prepare values
        values = []
        for field in fields:
            val = user_data.get(field)
            # Handle datetime objects
            if isinstance(val, datetime):
                val = val.isoformat()
            values.append(val)
            
        placeholders = ', '.join(['?'] * len(fields))
        
        # Upsert query
        query = f"""
            INSERT INTO users ({', '.join(fields)})
            VALUES ({placeholders})
            ON CONFLICT(user_id) DO UPDATE SET
                name=excluded.name,
                email=excluded.email,
                birth_date=excluded.birth_date,
                birth_time=excluded.birth_time,
                birth_place=excluded.birth_place,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                timezone=excluded.timezone,
                system=excluded.system,
                language=excluded.language,
                last_active=excluded.last_active
        """
        
        try:
            cursor.execute(query, values)
            conn.commit()
        except Exception as e:
            print(f"[DB] Error upserting user {user_id}: {e}")
            raise e
        finally:
            conn.close()

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user/profile by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None

    def user_exists(self, user_id: str) -> bool:
        """Check if user exists."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        
        conn.close()
        return exists

    def update_last_active(self, user_id: str):
        """Update last_active timestamp."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (now, user_id))
        
        conn.commit()
        conn.close()

    # =========================================================================
    # CONVERSATION OPERATIONS
    # =========================================================================

    def add_message(self, user_id: str, role: str, content: str, intent: str = None):
        """Log a message in the conversation history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversations (user_id, role, content, intent)
            VALUES (?, ?, ?, ?)
        """, (user_id, role, content, intent))
        
        conn.commit()
        conn.close()

    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        Get recent conversation history for context.
        
        Returns list of dicts: {'role': 'user', 'content': '...'}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get last N messages ordered by time
        cursor.execute("""
            SELECT role, content 
            FROM conversations 
            WHERE user_id = ? 
            ORDER BY id DESC 
            LIMIT ?
        """, (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Reverse to get chronological order (Oldest -> Newest)
        history = [dict(row) for row in rows]
        return history[::-1]
