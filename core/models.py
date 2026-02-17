# core/models.py
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional


class StyleMode(str, Enum):
    READABLE = "readable"
    COMPACT = "compact"


class OverallTestStatus(str, Enum):
    ALL_PASSED = "all_passed"
    SOME_FAILED = "some_failed"


class MemoryContext(BaseModel):
    preferred_language: str = "python"
    preferred_style_mode: StyleMode = StyleMode.READABLE
    common_mistakes: List[str] = []
    repeated_weaknesses: List[str] = []
    last_interaction_summary: Optional[str] = None


class PlanningOutput(BaseModel):
    summary: str


class CodeOutput(BaseModel):
    code: str


class TestingOutput(BaseModel):
    overall_status: OverallTestStatus
