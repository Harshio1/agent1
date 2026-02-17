# core/models.py

from pydantic import BaseModel
from enum import Enum
from typing import List, Optional, Any


# --------------------
# Enums
# --------------------

class StyleMode(str, Enum):
    READABLE = "readable"
    COMPACT = "compact"


class OverallTestStatus(str, Enum):
    ALL_PASSED = "all_passed"
    SOME_FAILED = "some_failed"


class SolutionApproach(str, Enum):
    DIRECT = "direct"
    ITERATIVE = "iterative"


class TestCaseType(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"


# --------------------
# Core data models
# --------------------

class MemoryContext(BaseModel):
    preferred_language: str = "python"
    preferred_style_mode: StyleMode = StyleMode.READABLE
    common_mistakes: List[str] = []
    repeated_weaknesses: List[str] = []
    last_interaction_summary: Optional[str] = None


class PlanningOutput(BaseModel):
    summary: str
    approach: Optional[SolutionApproach] = None


class CodeOutput(BaseModel):
    code: str


class TestCase(BaseModel):
    name: str
    type: TestCaseType
    input: Any = None
    expected_output: Any = None


class TestFailure(BaseModel):
    test_name: str
    reason: str


class TestingOutput(BaseModel):
    overall_status: OverallTestStatus
    failures: List[TestFailure] = []


class RootCauseAnalysis(BaseModel):
    explanation: str
    suggested_fix: Optional[str] = None


class DebugOutput(BaseModel):
    root_cause: RootCauseAnalysis
