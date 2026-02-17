from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class StepLogEntry(BaseModel):
    step_name: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    error: Optional[str] = None


class CoreState(BaseModel):
    state_version: str
    request_id: str
    raw_problem_input: str
    user_id: Optional[str] = None

    intent_result: Optional[object] = None
    planning_result: Optional[object] = None
    code_result: Optional[object] = None
    test_result: Optional[object] = None
    debug_result: Optional[object] = None
    memory_context: Optional[object] = None

    execution_log: List[StepLogEntry] = Field(default_factory=list)
