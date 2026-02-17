from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from langgraph.graph import END, START, StateGraph

# =======================
# ABSOLUTE CORE IMPORTS
# =======================

from core.models import (
    CodeOutput,
    DebugOutput,
    MemoryContext,
    OverallTestStatus,
    PlanningOutput,
    RootCauseAnalysis,
    SolutionApproach,
    StyleMode,
    TestCase,
    TestCaseType,
    TestFailure,
    TestingOutput,
)
from core.state import CoreState, StepLogEntry

# =======================
# ABSOLUTE AGENT IMPORTS
# =======================

from agents.intent_classifier import (
    IntentClassifierAgent,
    create_default_intent_classifier,
)
from agents.engineering_planner import (
    EngineeringPlannerAgent,
    create_default_engineering_planner,
)
from agents.coder import CoderAgent, create_default_coder
from agents.adversarial_tester import (
    AdversarialTesterAgent,
    create_default_adversarial_tester,
)
from agents.debugger import DebuggerAgent, create_default_debugger
from agents.memory_agent import MemoryAgent, create_default_memory_agent

# =======================
# ABSOLUTE MEMORY IMPORTS
# =======================

from memory.storage_base import MemoryStorage
from memory.sqlite_storage import SQLiteMemoryStorage, SQLiteConfig


MAX_DEBUG_ITERATIONS = 2


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _log_step(
    state: CoreState,
    step_name: str,
    started_at: datetime,
    error: str | None = None,
) -> CoreState:
    finished_at = _now_utc()
    duration_ms = max(
        0,
        int((finished_at - started_at).total_seconds() * 1000),
    )

    entry = StepLogEntry(
        step_name=step_name,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        input_summary=None,
        output_summary=None,
        error=error,
    )

    new_state = state.model_copy(deep=True)
    new_state.execution_log.append(entry)
    return new_state


def _count_debug_iterations(state: CoreState) -> int:
    return sum(1 for entry in state.execution_log if entry.step_name == "debugger")


def _default_memory_context() -> MemoryContext:
    return MemoryContext(
        preferred_language="python",
        preferred_style_mode=StyleMode.READABLE,
        common_mistakes=[],
        repeated_weaknesses=[],
        last_interaction_summary=None,
    )


# ---------------------------------------------------------------------------
# Memory nodes
# ---------------------------------------------------------------------------

def make_memory_load_node(storage: MemoryStorage) -> Callable[[CoreState], CoreState]:
    def memory_load(state: CoreState) -> CoreState:
        started_at = _now_utc()
        new_state = state.model_copy(deep=True)

        if new_state.user_id:
            new_state.memory_context = storage.load_context(new_state.user_id)
        elif new_state.memory_context is None:
            new_state.memory_context = _default_memory_context()

        return _log_step(new_state, "memory_load", started_at)

    return memory_load


_DEFAULT_MEMORY_AGENT: MemoryAgent | None = None


def _get_memory_agent() -> MemoryAgent:
    global _DEFAULT_MEMORY_AGENT
    if _DEFAULT_MEMORY_AGENT is None:
        _DEFAULT_MEMORY_AGENT = create_default_memory_agent()
    return _DEFAULT_MEMORY_AGENT


def make_memory_update_node(storage: MemoryStorage) -> Callable[[CoreState], CoreState]:
    def memory_update(state: CoreState) -> CoreState:
        started_at = _now_utc()
        new_state = state.model_copy(deep=True)

        if new_state.memory_context is None:
            new_state.memory_context = _default_memory_context()

        agent = _get_memory_agent()
        updates = agent.extract_updates(
            intent=new_state.intent_result,
            testing=new_state.test_result,
            debug=new_state.debug_result,
            existing_context=new_state.memory_context,
        )

        new_state.memory_context.last_interaction_summary = (
            updates.get("interaction_summary")
            or "Completed an end-to-end orchestration run."
        )

        if new_state.user_id:
            storage.update_preferences(
                user_id=new_state.user_id,
                preferred_language=updates.get("preferred_language"),
                preferred_style_mode=updates.get("preferred_style_mode"),
            )

            for mistake in updates.get("mistakes", []):
                storage.record_mistake(
                    user_id=new_state.user_id,
                    category=mistake.get("category", "general_bug"),
                    description=mistake.get("description", "Unspecified mistake"),
                )

        return _log_step(new_state, "memory_update", started_at)

    return memory_update


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

_DEFAULT_INTENT_CLASSIFIER: IntentClassifierAgent | None = None


def _get_intent_classifier() -> IntentClassifierAgent:
    global _DEFAULT_INTENT_CLASSIFIER
    if _DEFAULT_INTENT_CLASSIFIER is None:
        _DEFAULT_INTENT_CLASSIFIER = create_default_intent_classifier()
    return _DEFAULT_INTENT_CLASSIFIER


def intent_classifier(state: CoreState) -> CoreState:
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    agent = _get_intent_classifier()
    result = agent.classify(
        raw_problem_input=new_state.raw_problem_input,
        memory_context=new_state.memory_context,
    )
    new_state.intent_result = result
    return _log_step(new_state, "intent_classifier", started_at)


_DEFAULT_PLANNER: EngineeringPlannerAgent | None = None


def _get_planner() -> EngineeringPlannerAgent:
    global _DEFAULT_PLANNER
    if _DEFAULT_PLANNER is None:
        _DEFAULT_PLANNER = create_default_engineering_planner()
    return _DEFAULT_PLANNER


def planner(state: CoreState) -> CoreState:
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    if new_state.intent_result is None:
        raise ValueError("planner requires intent_result")

    agent = _get_planner()
    new_state.planning_result = agent.plan(
        intent=new_state.intent_result,
        raw_problem_input=new_state.raw_problem_input,
        memory_context=new_state.memory_context,
    )
    return _log_step(new_state, "planner", started_at)


_DEFAULT_CODER: CoderAgent | None = None


def _get_coder() -> CoderAgent:
    global _DEFAULT_CODER
    if _DEFAULT_CODER is None:
        _DEFAULT_CODER = create_default_coder()
    return _DEFAULT_CODER


def coder(state: CoreState) -> CoreState:
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    agent = _get_coder()
    new_state.code_result = agent.code(
        planning=new_state.planning_result,
        intent=new_state.intent_result,
        debug=new_state.debug_result,
    )
    return _log_step(new_state, "coder", started_at)


_DEFAULT_TESTER: AdversarialTesterAgent | None = None


def _get_tester() -> AdversarialTesterAgent:
    global _DEFAULT_TESTER
    if _DEFAULT_TESTER is None:
        _DEFAULT_TESTER = create_default_adversarial_tester()
    return _DEFAULT_TESTER


def tester(state: CoreState) -> CoreState:
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    agent = _get_tester()
    new_state.test_result = agent.test(
        planning=new_state.planning_result,
        code=new_state.code_result,
        intent=new_state.intent_result,
    )
    return _log_step(new_state, "tester", started_at)


_DEFAULT_DEBUGGER: DebuggerAgent | None = None


def _get_debugger() -> DebuggerAgent:
    global _DEFAULT_DEBUGGER
    if _DEFAULT_DEBUGGER is None:
        _DEFAULT_DEBUGGER = create_default_debugger()
    return _DEFAULT_DEBUGGER


def debugger(state: CoreState) -> CoreState:
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    agent = _get_debugger()
    new_state.debug_result = agent.debug(
        testing=new_state.test_result,
        planning=new_state.planning_result,
        code=new_state.code_result,
    )
    return _log_step(new_state, "debugger", started_at)


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def _route_after_tester(state: CoreState) -> str:
    if state.test_result is None:
        return "memory_update"

    if state.test_result.overall_status == OverallTestStatus.ALL_PASSED:
        return "memory_update"

    if _count_debug_iterations(state) >= MAX_DEBUG_ITERATIONS:
        return "memory_update"

    return "debugger"


def build_orchestration_graph(storage: MemoryStorage) -> StateGraph:
    graph: StateGraph[CoreState] = StateGraph(CoreState)

    graph.add_node("memory_load", make_memory_load_node(storage))
    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("planner", planner)
    graph.add_node("coder", coder)
    graph.add_node("tester", tester)
    graph.add_node("debugger", debugger)
    graph.add_node("memory_update", make_memory_update_node(storage))

    graph.add_edge(START, "memory_load")
    graph.add_edge("memory_load", "intent_classifier")
    graph.add_edge("intent_classifier", "planner")
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "tester")

    graph.add_conditional_edges(
        "tester",
        _route_after_tester,
        {
            "debugger": "debugger",
            "memory_update": "memory_update",
        },
    )

    graph.add_edge("debugger", "coder")
    graph.add_edge("memory_update", END)

    return graph


def compile_orchestration_graph(storage: MemoryStorage) -> Callable[[CoreState], CoreState]:
    graph = build_orchestration_graph(storage)
    app = graph.compile()
    return lambda state: app.invoke(state)


def create_default_sqlite_storage(db_path: str | Path) -> SQLiteMemoryStorage:
    return SQLiteMemoryStorage(SQLiteConfig(db_path=Path(db_path)))
