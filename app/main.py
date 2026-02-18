from fastapi import FastAPI
from pydantic import BaseModel
from pathlib import Path
from typing import Optional

from core.state import CoreState
from core.orchestration import (
    compile_orchestration_graph,
    create_default_sqlite_storage,
)

app = FastAPI(title="CodePilot API")

# ---------- HEALTH CHECK ----------
@app.get("/")
def root():
    return {"status": "ok", "service": "CodePilot API"}


# ---------- REQUEST MODEL ----------
class ProblemRequest(BaseModel):
    problem: str
    user_id: Optional[str] = None


# ---------- LAZY PIPELINE ----------
_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        storage = create_default_sqlite_storage(Path("memory.db"))
        _pipeline = compile_orchestration_graph(storage)
    return _pipeline


# ---------- SOLVE ----------
@app.post("/solve")
def solve_problem(request: ProblemRequest):
    run_pipeline = get_pipeline()

    state = CoreState(
        state_version="1.0",
        request_id="web_request",
        raw_problem_input=request.problem,
        user_id=request.user_id,
    )

    final_state = run_pipeline(state)

    return {
        "intent": final_state.intent_result,
        "plan": final_state.planning_result,
        "code": final_state.code_result,
        "tests": final_state.test_result,
        "debug": final_state.debug_result,
    }
