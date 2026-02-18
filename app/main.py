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

storage = None
run_pipeline = None


class ProblemRequest(BaseModel):
    problem: str
    user_id: Optional[str] = None


@app.on_event("startup")
def startup_event():
    global storage, run_pipeline

    storage = create_default_sqlite_storage(
        Path("/tmp/memory.db")  # Railway-safe path
    )

    run_pipeline = compile_orchestration_graph(storage)


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/solve")
def solve_problem(request: ProblemRequest):
    if run_pipeline is None:
        return {"error": "Pipeline not initialized"}

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
