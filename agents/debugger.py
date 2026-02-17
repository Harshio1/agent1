from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pydantic import ValidationError

from core.models import (
    CodeOutput,
    DebugOutput,
    FailureType,
    PlanningOutput,
    RootCauseAnalysis,
    TestFailure,
    TestingOutput,
    FixProposal,
)


@dataclass
class DebuggerConfig:
    """
    Configuration for the LLM-assisted DebuggerAgent.

    Attributes:
        model: Name of the chat completion model to use.
        max_retries: Number of attempts to obtain a valid, parseable response.
        temperature: Sampling temperature for the model.
    """

    model: str = "gpt-4.1-mini"
    max_retries: int = 2
    temperature: float = 0.1


class DebuggerAgent:
    """
    LLM-assisted debugger.

    Responsibilities:
      - Analyze test failures and relate them back to planning assumptions.
      - Identify likely root causes (logic, boundary, performance, assumption mismatch).
      - Propose high-level fix strategies for the CoderAgent (no code).
    """

    def __init__(
        self,
        client: OpenAI,
        config: Optional[DebuggerConfig] = None,
    ) -> None:
        self._client = client
        self._config = config or DebuggerConfig()

    def debug(
        self,
        testing: TestingOutput,
        planning: PlanningOutput,
        code: CodeOutput,
    ) -> DebugOutput:
        """
        Produce a DebugOutput given testing results, planning artifacts, and code.

        If LLM-based analysis fails, a deterministic, heuristic DebugOutput is
        generated instead.
        """
        # If there are no failed cases, return an empty debug result.
        if not testing.failed_cases:
            return DebugOutput(
                root_causes=[],
                proposed_fixes=[],
                selected_fix_id=None,
                updated_code_result=None,
                requires_user_input=False,
            )

        context = self._build_context_summary(testing, planning)

        last_error: Optional[Exception] = None
        for _attempt in range(self._config.max_retries + 1):
            try:
                raw_json = self._invoke_llm(
                    context_summary=context,
                    testing=testing,
                    planning=planning,
                )
                debug_output = DebugOutput.model_validate(raw_json)
                # Ensure we never accept updated_code_result from the model;
                # code changes are the responsibility of the CoderAgent.
                debug_output.updated_code_result = None
                return debug_output
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_error = exc
                continue

        # Fallback if LLM output cannot be validated.
        return self._heuristic_fallback(testing, planning, last_error)

    def _build_context_summary(
        self,
        testing: TestingOutput,
        planning: PlanningOutput,
    ) -> str:
        """
        Build a compact textual context that summarizes the failure landscape.
        """
        lines: List[str] = []
        lines.append(
            f"Number of test cases: {len(testing.test_cases)}, "
            f"passed: {len(testing.passed_cases)}, "
            f"failed: {len(testing.failed_cases)}."
        )
        if planning.assumptions:
            assumptions = "; ".join(planning.assumptions[:5])
            lines.append(f"Key assumptions: {assumptions}")

        # Provide a quick description of each failing case.
        failure_descriptions: List[str] = []
        tc_by_id: Dict[str, Any] = {tc.id: tc for tc in testing.test_cases}
        for failure in testing.failures:
            tc = tc_by_id.get(failure.case_id)
            if tc is not None:
                failure_descriptions.append(
                    f"[case_id={tc.id}, type={tc.type.value}] "
                    f"description={tc.description}, "
                    f"expected_behavior={tc.expected_behavior}, "
                    f"failure_type={failure.failure_type.value}, "
                    f"error_message={failure.error_message}"
                )
            else:
                failure_descriptions.append(
                    f"[case_id={failure.case_id}] "
                    f"failure_type={failure.failure_type.value}, "
                    f"error_message={failure.error_message}"
                )

        if failure_descriptions:
            combined = " | ".join(failure_descriptions[:5])
            lines.append(f"Failure summary: {combined}")

        return " ".join(lines)

    def _invoke_llm(
        self,
        context_summary: str,
        testing: TestingOutput,
        planning: PlanningOutput,
    ) -> Dict[str, Any]:
        """
        Call the underlying LLM and return a parsed JSON object suitable for
        DebugOutput.model_validate.
        """
        system_prompt = (
            "You are a debugging assistant for a software engineering agent "
            "called CodePilot.\n\n"
            "You receive:\n"
            "- A conceptual plan including explicit assumptions.\n"
            "- A summary of failing tests.\n\n"
            "Your task is ONLY to explain root causes and propose high level "
            "fix strategies. You must NOT write code or pseudocode.\n\n"
            "Respond with a STRICT JSON object matching this schema:\n\n"
            "{\n"
            '  \"root_causes\": [\n'
            "    {\n"
            '      \"id\": string,\n'
            '      \"description\": string,\n'
            '      \"failed_assumptions\": [list of strings drawn from or '
            "referencing the planning assumptions],\n"
            '      \"impacted_test_case_ids\": [list of failing test case ids]\n'
            "    },\n"
            "    ... at least one entry ...\n"
            "  ],\n"
            '  \"proposed_fixes\": [\n'
            "    {\n"
            '      \"id\": string,\n'
            '      \"target_root_cause_ids\": [list of root_causes ids],\n'
            '      \"description\": string,\n'
            '      \"notes_for_coder\": [list of concrete but non code level '
            "suggestions]\n"
            "    },\n"
            "    ... at least one entry ...\n"
            "  ],\n"
            '  \"selected_fix_id\": string or null,\n'
            '  \"updated_code_result\": null,\n'
            '  \"requires_user_input\": boolean\n'
            "}\n\n"
            "Important:\n"
            "- Do NOT include code or pseudocode.\n"
            "- Focus on conceptual explanations and guidance.\n"
            "- When mapping to failed_assumptions, prefer using the exact text "
            "of planning assumptions where applicable.\n"
            "Output ONLY the JSON object with no additional commentary."
        )

        # Serialize minimal testing/planning context for the model.
        testing_summary = {
            "failed_cases": [
                {
                    "case_id": f.case_id,
                    "failure_type": f.failure_type.value,
                    "error_message": f.error_message,
                }
                for f in testing.failures
            ],
            "assumptions": planning.assumptions,
        }

        user_prompt = (
            "Context summary:\n"
            f"{context_summary}\n\n"
            "Structured data:\n"
            f"{json.dumps(testing_summary, ensure_ascii=False)}"
        )

        response = self._client.chat.completions.create(
            model=self._config.model,
            temperature=self._config.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned empty content for debugging.")

        content = content.strip()
        return json.loads(content)

    def _heuristic_fallback(
        self,
        testing: TestingOutput,
        planning: PlanningOutput,
        error: Optional[Exception],
    ) -> DebugOutput:
        """
        Deterministic fallback when LLM-based debugging fails.
        """
        _ = error  # reserved for potential logging by orchestration.

        # Group failures by failure_type to create coarse root causes.
        failures_by_type: Dict[FailureType, List[TestFailure]] = {}
        for f in testing.failures:
            failures_by_type.setdefault(f.failure_type, []).append(f)

        root_causes: List[RootCauseAnalysis] = []
        proposed_fixes: List[FixProposal] = []

        assumptions = planning.assumptions or []
        default_assumption = assumptions[0] if assumptions else "Unspecified assumption"

        for idx, (failure_type, failure_list) in enumerate(failures_by_type.items(), start=1):
            case_ids = [f.case_id for f in failure_list]

            if failure_type == FailureType.TIMEOUT:
                description = (
                    "The solution appears to take too long on some inputs, "
                    "indicating potential performance or complexity issues."
                )
                failed_assumptions = [
                    a
                    for a in assumptions
                    if "time" in a.lower()
                    or "performance" in a.lower()
                    or "complexity" in a.lower()
                ] or [default_assumption]
            elif failure_type == FailureType.RESOURCE:
                description = (
                    "The solution seems to exceed resource limits, suggesting "
                    "inefficient memory or data structure usage."
                )
                failed_assumptions = [
                    a
                    for a in assumptions
                    if "memory" in a.lower()
                    or "space" in a.lower()
                    or "resource" in a.lower()
                ] or [default_assumption]
            else:
                description = (
                    "The solution returns incorrect results or raises errors for "
                    "some inputs, indicating a logic or boundary condition issue."
                )
                failed_assumptions = [
                    a
                    for a in assumptions
                    if "edge" in a.lower()
                    or "empty" in a.lower()
                    or "valid" in a.lower()
                ] or [default_assumption]

            rc_id = f"rc_{idx}"
            root_causes.append(
                RootCauseAnalysis(
                    id=rc_id,
                    description=description,
                    failed_assumptions=failed_assumptions,
                    impacted_test_case_ids=case_ids,
                )
            )

            if failure_type == FailureType.TIMEOUT:
                fix_desc = (
                    "Review the algorithm and data structures to reduce the "
                    "amount of work performed on large inputs, and consider "
                    "early termination where appropriate."
                )
                notes = [
                    "Revisit the selected approach to confirm its expected time behaviour.",
                    "Look for nested loops or repeated traversals that can be simplified.",
                ]
            elif failure_type == FailureType.RESOURCE:
                fix_desc = (
                    "Reduce peak memory usage by avoiding unnecessary copies "
                    "and using more compact representations where possible."
                )
                notes = [
                    "Identify large intermediate structures that can be streamed or reused.",
                    "Ensure data structures are cleared when no longer needed.",
                ]
            else:
                fix_desc = (
                    "Tighten handling of boundary conditions and validate "
                    "intermediate results against the problem's assumptions."
                )
                notes = [
                    "Add checks for empty or minimal inputs.",
                    "Verify index calculations and off by one boundaries.",
                ]

            fix_id = f"fix_{idx}"
            proposed_fixes.append(
                FixProposal(
                    id=fix_id,
                    target_root_cause_ids=[rc_id],
                    description=fix_desc,
                    notes_for_coder=notes,
                )
            )

        selected_fix_id = proposed_fixes[0].id if proposed_fixes else None

        return DebugOutput(
            root_causes=root_causes,
            proposed_fixes=proposed_fixes,
            selected_fix_id=selected_fix_id,
            updated_code_result=None,
            requires_user_input=False,
        )


def create_default_debugger() -> DebuggerAgent:
    """
    Convenience factory that builds a DebuggerAgent using environment variables
    for configuration.

    Environment variables:
      - CODEPILOT_DEBUGGER_MODEL: override default model name.
    """
    model = os.getenv("CODEPILOT_DEBUGGER_MODEL", DebuggerConfig.model)
    config = DebuggerConfig(model=model)
    client = OpenAI()
    return DebuggerAgent(client=client, config=config)

