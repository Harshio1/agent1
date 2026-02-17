import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.models import MemoryContext, StyleMode

from memory.storage_base import MemoryStorage


@dataclass
class SQLiteConfig:
    """Configuration for SQLiteMemoryStorage."""
    db_path: Path


class SQLiteMemoryStorage(MemoryStorage):
    """
    SQLite-based implementation of MemoryStorage.
    
    Stores user memory context in a SQLite database.
    """

    def __init__(self, config: SQLiteConfig):
        self.config = config
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema if it doesn't exist."""
        db_path = Path(self.config.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_contexts (
                    user_id TEXT PRIMARY KEY,
                    preferred_language TEXT,
                    preferred_style_mode TEXT,
                    common_mistakes TEXT,
                    repeated_weaknesses TEXT,
                    last_interaction_summary TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_mistakes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_contexts(user_id)
                )
            """)
            conn.commit()

    def load_context(self, user_id: str) -> Optional[MemoryContext]:
        """Load the memory context for a given user."""
        with sqlite3.connect(str(self.config.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_contexts WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            # Parse stored data
            preferred_language = row["preferred_language"] or "python"
            preferred_style_mode_str = row["preferred_style_mode"]
            preferred_style_mode = (
                StyleMode(preferred_style_mode_str)
                if preferred_style_mode_str
                else StyleMode.READABLE
            )
            
            # Parse JSON-like lists (stored as comma-separated strings for simplicity)
            common_mistakes = (
                row["common_mistakes"].split(",")
                if row["common_mistakes"]
                else []
            )
            repeated_weaknesses = (
                row["repeated_weaknesses"].split(",")
                if row["repeated_weaknesses"]
                else []
            )
            
            return MemoryContext(
                preferred_language=preferred_language,
                preferred_style_mode=preferred_style_mode,
                common_mistakes=[m.strip() for m in common_mistakes if m.strip()],
                repeated_weaknesses=[w.strip() for w in repeated_weaknesses if w.strip()],
                last_interaction_summary=row["last_interaction_summary"],
            )

    def update_preferences(
        self,
        user_id: str,
        preferred_language: Optional[str] = None,
        preferred_style_mode: Optional[StyleMode] = None,
    ) -> None:
        """Update user preferences."""
        with sqlite3.connect(str(self.config.db_path)) as conn:
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute(
                "SELECT user_id FROM user_contexts WHERE user_id = ?",
                (user_id,)
            )
            exists = cursor.fetchone() is not None
            
            if exists:
                updates = []
                params = []
                if preferred_language is not None:
                    updates.append("preferred_language = ?")
                    params.append(preferred_language)
                if preferred_style_mode is not None:
                    updates.append("preferred_style_mode = ?")
                    params.append(preferred_style_mode.value)
                
                if updates:
                    params.append(user_id)
                    cursor.execute(
                        f"UPDATE user_contexts SET {', '.join(updates)} WHERE user_id = ?",
                        params
                    )
            else:
                # Create new user context
                cursor.execute(
                    """INSERT INTO user_contexts 
                       (user_id, preferred_language, preferred_style_mode)
                       VALUES (?, ?, ?)""",
                    (
                        user_id,
                        preferred_language or "python",
                        preferred_style_mode.value if preferred_style_mode else StyleMode.READABLE.value,
                    )
                )
            
            conn.commit()

    def record_mistake(
        self,
        user_id: str,
        category: str,
        description: str,
    ) -> None:
        """Record a mistake for a user."""
        with sqlite3.connect(str(self.config.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO user_mistakes (user_id, category, description)
                   VALUES (?, ?, ?)""",
                (user_id, category, description)
            )
            conn.commit()
