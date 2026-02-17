from __future__ import annotations

import json
import multiprocessing as mp
import os
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from core.models import (
    CodeOutput,
    FailureType,
    IntentClassificationOutput,
    OverallTestStatus,
    PlanningOutput,
    TestCase,
    TestCaseType,
    TestFailure,
    TestingOutput,
)


@dataclass
class AdversarialTesterConfig:
    """
    Configuration for the LLM-assisted AdversarialTesterAgent.

    Attributes:
        model: Name of the chat completion model to use for test generation.
        max_retries: Number of attempts to obtain a valid test suite.
        temperature: Sampling temperature for the model.
        per_test_timeout_seconds: Maximum wall-clock time per test execution.
    """

    model: str = "gpt-4.1-mini"
    max_retries: int = 2
    temperature: float = 0.1
    per_test_timeout_seconds: float = 2.0


class _GeneratedTests(BaseModel):
    """
    Internal helper model for validating LLM-generated test cases.
    """

    test_cases: List[TestCase]


SAFE_BUILTINS: Dict[str, Any] = {
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "sorted": sorted,
    "enumerate": enumerate,
    "any": any,
    "all": all,
    "zip": zip,
    "map": map,
    "filter": filter,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
}


def _test_worker(
    source_files: Dict[str, str],
    entrypoint: str,
    input_payload: Any,
    result_queue: mp.Queue,
) -> None:
    """
    Execute the user's code in an isolated process and report the outcome.

    This function:
      - Executes all source files in a single namespace.
      - Locates the entrypoint function.
      - Invokes it with input_payload.
      - Sends a tuple (status, output, error_trace) via result_queue.
    """
    try:
        namespace: Dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
        for _, content in source_files.items():
            exec(content, namespace, namespace)

        # Entrypoint is expected to be in the form "module.function". We only
        # use the function name here, since all code was executed into a single
        # namespace for isolation.
        try:
            _, func_name = entrypoint.split(".", 1)
        except ValueError:
            raise RuntimeError(
                f"Entrypoint '{entrypoint}' is not in the form 'module.function'."
            )

        func = namespace.get(func_name)
        if not callable(func):
            raise RuntimeError(
                f"Entrypoint function '{func_name}' not found in executed code."
            )

        output = func(input_payload)
        result_queue.put(("ok", output, None))
    except Exception:
        result_queue.put(("error", None, traceback.format_exc()))


class AdversarialTesterAgent:
    """
    LLM-assisted adversarial tester.

    Responsibilities:
      - Derive a conceptual input/output contract from planning and intent.
      - Use an LLM to generate a diverse set of test cases.
      - Execute those tests in a sandboxed Python process with timeouts.
      - Summarize results into a TestingOutput instance.
    """

    def __init__(
        self,
        client: OpenAI,
        config: Optional[AdversarialTesterConfig] = None,
    ) -> None:
        self._client = client
        self._config = config or AdversarialTesterConfig()

    def test(
        self,
        planning: PlanningOutput,
        code: CodeOutput,
        intent: Optional[IntentClassificationOutput],
    ) -> TestingOutput:
        """
        Generate and execute adversarial tests for the given solution.

        If LLM-based test generation fails, falls back to a small deterministic
        test suite that exercises basic behaviors of the entrypoint function.
        """
        contract_summary = self._build_contract_summary(planning, intent)

        last_error: Optional[Exception] = None
        tests: Optional[_GeneratedTests] = None
        for _attempt in range(self._config.max_retries + 1):
            try:
                raw_json = self._invoke_llm(
                    contract_summary=contract_summary,
                    code=code,
                )
                tests = _GeneratedTests.model_validate(raw_json)
                break
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_error = exc
                continue

        if tests is None:
            tests = self._heuristic_fallback_tests(code, last_error)

        return self._execute_tests(code, tests.test_cases)

    def _build_contract_summary(
        self,
        planning: PlanningOutput,
        intent: Optional[IntentClassificationOutput],
    ) -> str:
        """
        Create a compact textual summary of the inferred input/output contract.
        """
        lines: List[str] = []
        if intent is not None:
            lines.append(
                f"Problem type: {intent.problem_type.value}, "
                f"context: {intent.context.value}."
            )

        lines.append(f"Restated problem: {planning.problem_restated}")

        if planning.assumptions:
            assumptions = "; ".join(planning.assumptions[:5])
            lines.append(f"Key assumptions: {assumptions}")

        selected = None
        for approach in planning.approaches:
            if approach.id == planning.selected_approach_id:
                selected = approach
                break

        if selected is not None:
            lines.append(f"Selected approach: {selected.name}")
            if selected.high_level_steps:
                steps = "; ".join(selected.high_level_steps[:4])
                lines.append(f"High level steps: {steps}")

        lines.append(
            "The solution exposes a single entrypoint that accepts one input "
            "value (which can be a scalar or JSON like structure) and returns "
            "one output value."
        )

        return " ".join(lines)

    def _invoke_llm(
        self,
        contract_summary: str,
        code: CodeOutput,
    ) -> Dict[str, Any]:
        """
        Ask the LLM to propose a suite of test cases as pure JSON.
        """
        system_prompt = (
            "You are an adversarial test designer for a software engineering "
            "assistant called CodePilot.\n\n"
            "Your task is to design a set of tests for a single function based "
            "on its conceptual contract. You must NOT write any code or "
            "pseudocode, only JSON descriptions of tests.\n\n"
            "Respond with a STRICT JSON object:\n\n"
            "{\n"
            '  \"test_cases\": [\n'
            "    {\n"
            '      \"id\": string,\n'
            '      \"description\": string,\n'
            '      \"input_payload\": any JSON value,\n'
            '      \"expected_behavior\": string,\n'
            '      \"type\": one of [\"unit\", \"edge\", \"stress\", \"property\"]\n'
            "    },\n"
            "    ... at least 6 test cases covering happy path, edge cases, "
            "stress inputs, and property style checks ...\n"
            "  ]\n"
            "}\n\n"
            "Important:\n"
            "- Do NOT include code, pseudocode, or language specific APIs.\n"
            "- Describe expected behavior in natural language.\n"
            "- Use simple JSON types only (numbers, strings, lists, objects).\n"
            "- The function has the signature: single input value -> single output value.\n"
            "Output ONLY the JSON object, with no additional commentary."
        )

        user_prompt = (
            "Conceptual contract for the function under test:\n"
            f"{contract_summary}\n\n"
            f"Entrypoint: {code.entrypoint}\n"
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
            raise ValueError("LLM returned empty content for adversarial testing.")

        content = content.strip()
        return json.loads(content)

    def _heuristic_fallback_tests(
        self,
        code: CodeOutput,
        error: Optional[Exception],
    ) -> _GeneratedTests:
        """
        Deterministic fallback tests when LLM based generation fails.
        """
        _ = error  # reserved for potential logging by orchestration.

        cases: List[TestCase] = [
            TestCase(
                id="fallback_unit_scalar",
                description="Simple scalar input to verify basic behavior.",
                input_payload=1,
                expected_behavior="The function should process a basic numeric input "
                "without raising errors.",
                type=TestCaseType.UNIT,
            ),
            TestCase(
                id="fallback_unit_object",
                description="Small JSON like mapping input.",
                input_payload={"value": 10},
                expected_behavior="The function should accept and return a structured "
                "value without structural corruption.",
                type=TestCaseType.UNIT,
            ),
            TestCase(
                id="fallback_edge_empty_list",
                description="Empty list to exercise boundary handling.",
                input_payload=[],
                expected_behavior="The function should handle an empty collection "
                "without failing.",
                type=TestCaseType.EDGE,
            ),
            TestCase(
                id="fallback_edge_large_list",
                description="Moderately large list to exercise performance.",
                input_payload=list(range(10000)),
                expected_behavior="The function should complete within the time "
                "limit without exhausting resources.",
                type=TestCaseType.STRESS,
            ),
        ]

        return _GeneratedTests(test_cases=cases)

    def _execute_tests(
        self,
        code: CodeOutput,
        test_cases: List[TestCase],
    ) -> TestingOutput:
        """
        Execute the given test cases in isolated processes and collect results.
        """
        passed_ids: List[str] = []
        failed_ids: List[str] = []
        failures: List[TestFailure] = []

        for case in test_cases:
            queue: mp.Queue = mp.Queue()
            proc = mp.Process(
                target=_test_worker,
                args=(code.source_files, code.entrypoint, case.input_payload, queue),
            )
            proc.start()
            proc.join(timeout=self._config.per_test_timeout_seconds)

            if proc.is_alive():
                proc.terminate()
                proc.join()
                failed_ids.append(case.id)
                failures.append(
                    TestFailure(
                        case_id=case.id,
                        failure_type=FailureType.TIMEOUT,
                        error_message=(
                            f"Test exceeded timeout of "
                            f"{self._config.per_test_timeout_seconds} seconds."
                        ),
                        stack_trace=None,
                        actual_output=None,
                    )
                )
                continue

            try:
                status, output, error_trace = queue.get_nowait()
            except Exception:
                status, output, error_trace = "error", None, "No result returned."

            if status == "ok":
                passed_ids.append(case.id)
                # For now we do not perform semantic comparison against
                # expected_behavior, which remains a descriptive field.
            else:
                failed_ids.append(case.id)
                failures.append(
                    TestFailure(
                        case_id=case.id,
                        failure_type=FailureType.EXCEPTION,
                        error_message="Execution raised an exception.",
                        stack_trace=error_trace,
                        actual_output=None,
                    )
                )

        if not test_cases:
            overall_status = OverallTestStatus.EXECUTION_ERROR
        elif failed_ids and passed_ids:
            overall_status = OverallTestStatus.PARTIALLY_FAILED
        elif failed_ids and not passed_ids:
            overall_status = OverallTestStatus.ALL_FAILED
        else:
            overall_status = OverallTestStatus.ALL_PASSED

        return TestingOutput(
            test_cases=test_cases,
            passed_cases=passed_ids,
            failed_cases=failed_ids,
            failures=failures,
            overall_status=overall_status,
        )


def create_default_adversarial_tester() -> AdversarialTesterAgent:
    """
    Convenience factory that builds an AdversarialTesterAgent using
    environment variables for configuration.

    Environment variables:
      - CODEPILOT_TESTER_MODEL: override default model name.
    """
    model = os.getenv("CODEPILOT_TESTER_MODEL", AdversarialTesterConfig.model)
    config = AdversarialTesterConfig(model=model)
    client = OpenAI()
    return AdversarialTesterAgent(client=client, config=config)

