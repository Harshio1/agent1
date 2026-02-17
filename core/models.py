# core/models.py

from pydantic import BaseModel
from enum import Enum
from typing import List, Optional, Any, Dict


# --------------------
# Enums
# --------------------

class StyleMode(str, Enum):
    READABLE = "readable"
    COMPACT = "compact"
    COMPETITIVE = "competitive"
    ENTERPRISE = "enterprise"


class OverallTestStatus(str, Enum):
    ALL_PASSED = "all_passed"
    SOME_FAILED = "some_failed"
    PARTIALLY_FAILED = "partially_failed"
    ALL_FAILED = "all_failed"
    EXECUTION_ERROR = "execution_error"


class ProblemType(str, Enum):
    DSA = "dsa"
    SYSTEM = "system"
    BUG_FIX = "bug_fix"
    OPTIMIZATION = "optimization"
    OTHER = "other"


class ProblemContext(str, Enum):
    INTERVIEW = "interview"
    PRODUCTION = "production"
    LEARNING = "learning"
    EXPERIMENTAL = "experimental"
    UNKNOWN = "unknown"


class TestCaseType(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    EDGE = "edge"
    STRESS = "stress"
    PROPERTY = "property"


class FailureType(str, Enum):
    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    RESOURCE = "resource"
    LOGIC_ERROR = "logic_error"


# --------------------
# Core data models
# --------------------

class MemoryContext(BaseModel):
    preferred_language: str = "python"
    preferred_style_mode: StyleMode = StyleMode.READABLE
    common_mistakes: List[str] = []
    repeated_weaknesses: List[str] = []
    last_interaction_summary: Optional[str] = None


class IntentConstraints(BaseModel):
    time_complexity_target: Optional[str] = None
    space_complexity_target: Optional[str] = None
    memory_limit_mb: Optional[int] = None
    time_budget_ms: Optional[int] = None
    additional_constraints: List[str] = []


class StylePreferences(BaseModel):
    language: Optional[str] = None
    style_mode: Optional[StyleMode] = None


class IntentClassificationOutput(BaseModel):
    problem_type: ProblemType
    context: ProblemContext
    languages: List[str]
    constraints: IntentConstraints
    style_preferences: StylePreferences
    confidence: float
    raw_json: Optional[Dict[str, Any]] = None


class SolutionApproach(BaseModel):
    id: str
    name: str
    high_level_steps: List[str]
    complexity_estimate: Dict[str, str]
    pros: List[str]
    cons: List[str]
    suitable_for: List[str]


class PlanningOutput(BaseModel):
    problem_restated: str
    assumptions: List[str]
    approaches: List[SolutionApproach]
    selected_approach_id: str
    selected_approach_justification: str


class CodeOutput(BaseModel):
    language: str
    style_mode: StyleMode
    source_files: Dict[str, str]
    entrypoint: str
    notes_for_tester: List[str]


class TestCase(BaseModel):
    id: str
    description: str
    input_payload: Any
    expected_behavior: str
    type: TestCaseType


class TestFailure(BaseModel):
    case_id: str
    failure_type: FailureType
    error_message: str
    stack_trace: Optional[str] = None
    actual_output: Optional[Any] = None


class TestingOutput(BaseModel):
    test_cases: List[TestCase]
    passed_cases: List[str] = []
    failed_cases: List[str] = []
    failures: List[TestFailure] = []
    overall_status: OverallTestStatus


class RootCauseAnalysis(BaseModel):
    id: str
    description: str
    failed_assumptions: List[str]
    impacted_test_case_ids: List[str]


class FixProposal(BaseModel):
    id: str
    target_root_cause_ids: List[str]
    description: str
    notes_for_coder: List[str]


class DebugOutput(BaseModel):
    root_causes: List[RootCauseAnalysis] = []
    proposed_fixes: List[FixProposal] = []
    selected_fix_id: Optional[str] = None
    updated_code_result: Optional[CodeOutput] = None
    requires_user_input: bool = False
