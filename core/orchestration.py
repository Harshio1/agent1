from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from langgraph.graph import END, START, StateGraph

from .models import (
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
from .state import CoreState, StepLogEntry
from ..agents.intent_classifier import IntentClassifierAgent, create_default_intent_classifier
from ..agents.engineering_planner import (
    EngineeringPlannerAgent,
    create_default_engineering_planner,
)
from ..agents.coder import CoderAgent, create_default_coder
from ..agents.adversarial_tester import (
    AdversarialTesterAgent,
    create_default_adversarial_tester,
)
from ..agents.debugger import DebuggerAgent, create_default_debugger
from ..agents.memory_agent import MemoryAgent, create_default_memory_agent
from ..memory.storage_base import MemoryStorage
from ..memory.sqlite_storage import SQLiteMemoryStorage, SQLiteConfig


MAX_DEBUG_ITERATIONS = 2


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _log_step(
    state: CoreState,
    step_name: str,
    started_at: datetime,
    error: str | None = None,
) -> CoreState:
    """
    Append a StepLogEntry for the given step.

    This helper assumes the caller is responsible for tracking the start time.
    """
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
    """Count how many times the debugger step has been executed."""
    return sum(1 for entry in state.execution_log if entry.step_name == "debugger")


def _default_memory_context() -> MemoryContext:
    """
    Construct an in-memory default MemoryContext.

    Used when no user_id is provided and therefore persistence is not possible.
    """
    return MemoryContext(
        preferred_language="python",
        preferred_style_mode=StyleMode.READABLE,
        common_mistakes=[],
        repeated_weaknesses=[],
        last_interaction_summary=None,
    )


# ---------------------------------------------------------------------------
# MemoryAgent nodes (bound to a MemoryStorage instance)
# ---------------------------------------------------------------------------


def make_memory_load_node(storage: MemoryStorage) -> Callable[[CoreState], CoreState]:
    """
    Create a MemoryAgent load node bound to a specific MemoryStorage.

    Behavior:
      - If user_id is present, loads a persistent MemoryContext from storage.
      - If user_id is absent, initializes a default in-memory MemoryContext.
    """

    def memory_load(state: CoreState) -> CoreState:
        started_at = _now_utc()
        new_state = state.model_copy(deep=True)

        if new_state.user_id:
            new_state.memory_context = storage.load_context(new_state.user_id)
        elif new_state.memory_context is None:
            new_state.memory_context = _default_memory_context()

        new_state = _log_step(new_state, "memory_load", started_at)
        return new_state

    return memory_load


_DEFAULT_MEMORY_AGENT: MemoryAgent | None = None


def _get_memory_agent() -> MemoryAgent:
    """
    Lazily construct a default MemoryAgent instance.

    This keeps orchestration code simple while still allowing dependency
    injection in tests by overriding the module-level variable if desired.
    """
    global _DEFAULT_MEMORY_AGENT
    if _DEFAULT_MEMORY_AGENT is None:
        _DEFAULT_MEMORY_AGENT = create_default_memory_agent()
    return _DEFAULT_MEMORY_AGENT


def make_memory_update_node(
    storage: MemoryStorage,
) -> Callable[[CoreState], CoreState]:
    """
    Create a MemoryAgent update node bound to a specific MemoryStorage.

    Behavior:
      - Uses an LLM-backed MemoryAgent to extract preferences and weaknesses
        from execution outputs.
      - Always updates CoreState.memory_context.last_interaction_summary.
      - If user_id is present, persists preferences and recorded mistakes to
        the provided MemoryStorage.
    """

    def memory_update(state: CoreState) -> CoreState:
        started_at = _now_utc()
        new_state = state.model_copy(deep=True)

        if new_state.memory_context is None:
            new_state.memory_context = _default_memory_context()

        # Use LLM-backed MemoryAgent to extract structured updates.
        agent = _get_memory_agent()
        updates = agent.extract_updates(
            intent=new_state.intent_result,
            testing=new_state.test_result,
            debug=new_state.debug_result,
            existing_context=new_state.memory_context,
        )

        # Update in-memory context with extracted summary.
        new_state.memory_context.last_interaction_summary = (
            updates.get("interaction_summary")
            or "Completed an end-to-end orchestration run."
        )

        # Persist memory only when we have a stable user_id.
        if new_state.user_id:
            storage.update_preferences(
                user_id=new_state.user_id,
                preferred_language=updates.get("preferred_language"),
                preferred_style_mode=updates.get("preferred_style_mode"),
            )

            # Record extracted mistakes.
            for mistake in updates.get("mistakes", []):
                storage.record_mistake(
                    user_id=new_state.user_id,
                    category=mistake.get("category", "general_bug"),
                    description=mistake.get("description", "Unspecified mistake"),
                )

        new_state = _log_step(new_state, "memory_update", started_at)
        return new_state

    return memory_update


# ---------------------------------------------------------------------------
# Intent classifier node (LLM-backed agent)
# ---------------------------------------------------------------------------

_DEFAULT_INTENT_CLASSIFIER: IntentClassifierAgent | None = None


def _get_intent_classifier() -> IntentClassifierAgent:
    """
    Lazily construct a default IntentClassifierAgent instance.

    This keeps orchestration code simple while still allowing dependency
    injection in tests by overriding the module-level variable if desired.
    """
    global _DEFAULT_INTENT_CLASSIFIER
    if _DEFAULT_INTENT_CLASSIFIER is None:
        _DEFAULT_INTENT_CLASSIFIER = create_default_intent_classifier()
    return _DEFAULT_INTENT_CLASSIFIER


def intent_classifier(state: CoreState) -> CoreState:
    """
    Real IntentClassifierAgent step.

    Uses an LLM-backed classifier with strict Pydantic validation to populate
    IntentClassificationOutput based only on raw_problem_input and
    memory_context.
    """
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    agent = _get_intent_classifier()

    try:
        result = agent.classify(
            raw_problem_input=new_state.raw_problem_input,
            memory_context=new_state.memory_context,
        )
        new_state.intent_result = result
        new_state = _log_step(new_state, "intent_classifier", started_at)
        return new_state
    except Exception as exc:
        # In the unlikely event the classifier fails completely, fall back to
        # a minimal, safe default to keep the pipeline running.
        error_msg = f"intent_classifier_error: {exc}"
        new_state = _log_step(new_state, "intent_classifier", started_at, error=error_msg)
        raise


# ---------------------------------------------------------------------------
# Engineering planner node (LLM-backed agent)
# ---------------------------------------------------------------------------


_DEFAULT_PLANNER: EngineeringPlannerAgent | None = None


def _get_planner() -> EngineeringPlannerAgent:
    """
    Lazily construct a default EngineeringPlannerAgent instance.

    This keeps orchestration code simple while still allowing dependency
    injection in tests by overriding the module-level variable if desired.
    """
    global _DEFAULT_PLANNER
    if _DEFAULT_PLANNER is None:
        _DEFAULT_PLANNER = create_default_engineering_planner()
    return _DEFAULT_PLANNER


def planner(state: CoreState) -> CoreState:
    """
    Real EngineeringPlannerAgent step.

    Uses an LLM-backed planner with strict Pydantic validation to populate
    PlanningOutput based only on the intent classification, raw problem input,
    and memory context.
    """
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    if new_state.intent_result is None:
        error_msg = "planner requires intent_result to be set before invocation."
        new_state = _log_step(new_state, "planner", started_at, error=error_msg)
        raise ValueError(error_msg)

    agent = _get_planner()

    try:
        planning_output = agent.plan(
            intent=new_state.intent_result,
            raw_problem_input=new_state.raw_problem_input,
            memory_context=new_state.memory_context,
        )
        new_state.planning_result = planning_output
        new_state = _log_step(new_state, "planner", started_at)
        return new_state
    except Exception as exc:
        error_msg = f"planner_error: {exc}"
        new_state = _log_step(new_state, "planner", started_at, error=error_msg)
        raise


_DEFAULT_CODER: CoderAgent | None = None
_DEFAULT_TESTER: AdversarialTesterAgent | None = None


def _get_coder() -> CoderAgent:
    """
    Lazily construct a default CoderAgent instance.

    This keeps orchestration code simple while still allowing dependency
    injection in tests by overriding the module-level variable if desired.
    """
    global _DEFAULT_CODER
    if _DEFAULT_CODER is None:
        _DEFAULT_CODER = create_default_coder()
    return _DEFAULT_CODER


def coder(state: CoreState) -> CoreState:
    """
    Real CoderAgent step.

    Uses an LLM-backed coder to generate Python code strictly according to the
    selected planning approach, style preferences, and an optional selected fix
    from debugging.
    """
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    if new_state.planning_result is None:
        error_msg = "coder requires planning_result to be set before invocation."
        new_state = _log_step(new_state, "coder", started_at, error=error_msg)
        raise ValueError(error_msg)

    agent = _get_coder()

    try:
        code_output = agent.code(
            planning=new_state.planning_result,
            intent=new_state.intent_result,
            debug=new_state.debug_result,
        )
        new_state.code_result = code_output
        new_state = _log_step(new_state, "coder", started_at)
        return new_state
    except Exception as exc:
        error_msg = f"coder_error: {exc}"
        new_state = _log_step(new_state, "coder", started_at, error=error_msg)
        raise


def _get_tester() -> AdversarialTesterAgent:
    """
    Lazily construct a default AdversarialTesterAgent instance.

    This keeps orchestration code simple while still allowing dependency
    injection in tests by overriding the module-level variable if desired.
    """
    global _DEFAULT_TESTER
    if _DEFAULT_TESTER is None:
        _DEFAULT_TESTER = create_default_adversarial_tester()
    return _DEFAULT_TESTER


def tester(state: CoreState) -> CoreState:
    """
    Real AdversarialTesterAgent step.

    Uses an LLM-assisted tester and a sandboxed Python runner to execute tests
    derived from the planning output, code output, and intent classification.
    """
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    if new_state.planning_result is None or new_state.code_result is None:
        error_msg = (
            "tester requires both planning_result and code_result to be set "
            "before invocation."
        )
        new_state = _log_step(new_state, "tester", started_at, error=error_msg)
        raise ValueError(error_msg)

    agent = _get_tester()

    try:
        testing_output = agent.test(
            planning=new_state.planning_result,
            code=new_state.code_result,
            intent=new_state.intent_result,
        )
        new_state.test_result = testing_output
        new_state = _log_step(new_state, "tester", started_at)
        return new_state
    except Exception as exc:
        error_msg = f"tester_error: {exc}"
        new_state = _log_step(new_state, "tester", started_at, error=error_msg)
        raise


_DEFAULT_DEBUGGER: DebuggerAgent | None = None


def _get_debugger() -> DebuggerAgent:
    """
    Lazily construct a default DebuggerAgent instance.

    This keeps orchestration code simple while still allowing dependency
    injection in tests by overriding the module-level variable if desired.
    """
    global _DEFAULT_DEBUGGER
    if _DEFAULT_DEBUGGER is None:
        _DEFAULT_DEBUGGER = create_default_debugger()
    return _DEFAULT_DEBUGGER


def debugger(state: CoreState) -> CoreState:
    """
    Real DebuggerAgent step.

    Uses an LLM-assisted debugger to convert test failures and planning
    assumptions into root-cause analyses and fix proposals.
    """
    started_at = _now_utc()
    new_state = state.model_copy(deep=True)

    if new_state.test_result is None or new_state.planning_result is None or new_state.code_result is None:
        error_msg = (
            "debugger requires test_result, planning_result, and code_result "
            "to be set before invocation."
        )
        new_state = _log_step(new_state, "debugger", started_at, error=error_msg)
        raise ValueError(error_msg)

    agent = _get_debugger()

    try:
        debug_output = agent.debug(
            testing=new_state.test_result,
            planning=new_state.planning_result,
            code=new_state.code_result,
        )
        new_state.debug_result = debug_output
        new_state = _log_step(new_state, "debugger", started_at)
        return new_state
    except Exception as exc:
        error_msg = f"debugger_error: {exc}"
        new_state = _log_step(new_state, "debugger", started_at, error=error_msg)
        raise


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def _route_after_tester(state: CoreState) -> str:
    """
    Decide whether to invoke the debugger or proceed directly to memory_update.

    Debugger runs only if tests did not fully pass and the maximum number of
    debug iterations has not been reached.
    """
    if state.test_result is None:
        return "memory_update"

    if state.test_result.overall_status == OverallTestStatus.ALL_PASSED:
        return "memory_update"

    debug_count = _count_debug_iterations(state)
    if debug_count >= MAX_DEBUG_ITERATIONS:
        return "memory_update"

    return "debugger"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_orchestration_graph(storage: MemoryStorage) -> StateGraph:
    """
    Build the LangGraph StateGraph representing the orchestration pipeline.

    Nodes:
      - memory_load
      - intent_classifier
      - planner
      - coder
      - tester
      - debugger
      - memory_update

    Control flow:
      memory_load -> intent_classifier -> planner -> coder -> tester
      After tester: either debugger (if tests failed and within debug bounds)
      or memory_update (if tests passed or debug limit reached).
      If debugger is taken, flow goes debugger -> coder -> tester and repeats,
      bounded by MAX_DEBUG_ITERATIONS.
    """
    graph: StateGraph[CoreState] = StateGraph(CoreState)

    memory_load_node = make_memory_load_node(storage)
    memory_update_node = make_memory_update_node(storage)

    graph.add_node("memory_load", memory_load_node)
    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("planner", planner)
    graph.add_node("coder", coder)
    graph.add_node("tester", tester)
    graph.add_node("debugger", debugger)
    graph.add_node("memory_update", memory_update_node)

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


def compile_orchestration_graph(
    storage: MemoryStorage,
) -> Callable[[CoreState], CoreState]:
    """
    Compile the orchestration graph into a callable for execution.

    The returned callable accepts an initial CoreState and returns the final
    CoreState after running through the graph.
    """
    graph = build_orchestration_graph(storage)
    app = graph.compile()

    def run(state: CoreState) -> CoreState:
        return app.invoke(state)

    return run


def create_default_sqlite_storage(db_path: str | Path) -> SQLiteMemoryStorage:
    """
    Convenience factory for creating a SQLiteMemoryStorage instance.

    Callers (CLI/API) can use this to obtain a concrete MemoryStorage while
    keeping orchestration parameterized over the abstract interface.
    """
    config = SQLiteConfig(db_path=Path(db_path))
    return SQLiteMemoryStorage(config=config)
