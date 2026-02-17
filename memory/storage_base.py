from abc import ABC, abstractmethod
from typing import Optional

from core.models import MemoryContext, StyleMode


class MemoryStorage(ABC):
    """
    Abstract base class for memory storage backends.
    
    Provides methods to load and update user context, preferences, and mistakes.
    """

    @abstractmethod
    def load_context(self, user_id: str) -> Optional[MemoryContext]:
        """
        Load the memory context for a given user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            MemoryContext if found, None otherwise
        """
        pass

    @abstractmethod
    def update_preferences(
        self,
        user_id: str,
        preferred_language: Optional[str] = None,
        preferred_style_mode: Optional[StyleMode] = None,
    ) -> None:
        """
        Update user preferences.
        
        Args:
            user_id: Unique identifier for the user
            preferred_language: Preferred programming language
            preferred_style_mode: Preferred code style mode
        """
        pass

    @abstractmethod
    def record_mistake(
        self,
        user_id: str,
        category: str,
        description: str,
    ) -> None:
        """
        Record a mistake for a user.
        
        Args:
            user_id: Unique identifier for the user
            category: Category of the mistake
            description: Description of the mistake
        """
        pass
