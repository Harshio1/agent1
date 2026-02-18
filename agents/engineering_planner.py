from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI
from pydantic import ValidationError

from core.models import (
    IntentClassificationOutput,
    MemoryContext,
    PlanningOutput,
    SolutionApproach,
)


@dataclass
class EngineeringPlannerConfig:
    """
    Configuration for the LLM-backed EngineeringPlannerAgent.

    Attributes:
        model: Name of the chat completion model to use.
        max_retries: Number of attempts to obtain a valid, parseable response.
        temperature: Sampling temperature for the model.
    """

    model: str = "gpt-4.1-mini"
    max_retries: int = 2
    temperature: float = 0.2


class EngineeringPlannerAgent:
    """
    LLM-backed engineering planner.

    Responsibilities:
      - Read only intent classification, raw problem text, and memory context.
      - Produce a validated PlanningOutput with multiple SolutionApproaches,
        trade-off analysis, and a selected approach with justification.
      - Maintain a hard guardrail against code-like content; any such content
        will cause validation to fail and trigger retries or fallback.
    """

    def __init__(
        self,
        client: OpenAI,
        config: Optional[EngineeringPlannerConfig] = None,
    ) -> None:
        self._client = client
        self._config = config or EngineeringPlannerConfig()

    def plan(
        self,
        intent: IntentClassificationOutput,
        raw_problem_input: str,
        memory_context: Optional[MemoryContext],
    ) -> PlanningOutput:
        """
        Generate a high-level engineering plan for the given problem.

        This method attempts multiple times to obtain a valid JSON object that
        conforms to PlanningOutput. If validation repeatedly fails, a safe
        deterministic fallback plan is used.
        """
        memory_hint = self._build_memory_hint(memory_context)
        intent_summary = self._summarize_intent(intent)

        last_error: Optional[Exception] = None
        for attempt in range(self._config.max_retries + 1):
            try:
                raw_json = self._invoke_llm(
                    raw_problem_input=raw_problem_input,
                    intent_summary=intent_summary,
                    memory_hint=memory_hint,
                )
                planning_output = PlanningOutput.model_validate(raw_json)
                return planning_output
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_error = exc
                # On retry we simply loop; the prompt remains strict about format.
                continue

        # Fallback to a deterministic, safe plan if LLM output cannot be validated.
        return self._heuristic_fallback(
            raw_problem_input=raw_problem_input,
            intent=intent,
            error=last_error,
        )

    def _build_memory_hint(self, memory_context: Optional[MemoryContext]) -> str:
        if memory_context is None:
            return "No detailed user memory is available."

        parts = []
        if memory_context.preferred_language:
            parts.append(f"Preferred language: {memory_context.preferred_language}.")
        if memory_context.preferred_style_mode:
            parts.append(
                f"Preferred style_mode: {memory_context.preferred_style_mode.value}."
            )
        if memory_context.repeated_weaknesses:
            weaknesses = ", ".join(memory_context.repeated_weaknesses[:5])
            parts.append(f"User weaknesses to be mindful of: {weaknesses}.")

        return " ".join(parts) if parts else "No detailed user memory is available."

    def _summarize_intent(self, intent: IntentClassificationOutput) -> str:
        return (
            f"problem_type={intent.problem_type.value}, "
            f"context={intent.context.value}, "
            f"languages={intent.languages}, "
            f"constraints={intent.constraints.model_dump()}"
        )

    def _invoke_llm(
        self,
        raw_problem_input: str,
        intent_summary: str,
        memory_hint: str,
    ) -> dict[str, Any]:
        """
        Call the underlying LLM and return a parsed JSON object suitable for
        PlanningOutput.model_validate.
        """
        system_prompt = (
            "You are an engineering planner for a software engineering assistant "
            "called CodePilot.\n\n"
            "Your ONLY task is to create a conceptual plan for solving a programming "
            "problem. You must NOT write any code, pseudocode, or use code-like "
            "tokens (such as 'def', 'class', 'import', '{', '}', ';', or '=>').\n\n"
            "Respond with a STRICT JSON object matching this schema:\n\n"
            "{\n"
            '  \"problem_restated\": string,\n'
            '  \"assumptions\": [list of strings],\n'
            '  \"approaches\": [\n'
            "    {\n"
            '      \"id\": string,\n'
            '      \"name\": string,\n'
            '      \"high_level_steps\": [list of strings],\n'
            '      \"complexity_estimate\": {\"time\": string, \"space\": string},\n'
            '      \"pros\": [list of strings],\n'
            '      \"cons\": [list of strings],\n'
            '      \"suitable_for\": [list of strings]\n'
            "    },\n"
            "    ... at least 2 approaches total ...\n"
            "  ],\n"
            '  \"selected_approach_id\": string,\n'
            '  \"selected_approach_justification\": string\n'
            "}\n\n"
            "Important guardrails:\n"
            "- Keep the content conceptual and descriptive only.\n"
            "- Do NOT include any language-specific APIs, keywords, or code-like "
            "syntax.\n"
            "- Focus on algorithms, data structures, and design choices in natural "
            "language.\n"
            "- The selected_approach_justification must explicitly mention trade-offs.\n\n"
            "Output ONLY the JSON object. Do not include explanations, comments, "
            "or any text before or after the JSON."
        )

        user_prompt = (
            f"Intent summary: {intent_summary}\n"
            f"User memory: {memory_hint}\n\n"
            "User problem description:\n"
            f"{raw_problem_input}\n"
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
            raise ValueError("LLM returned empty content for engineering planning.")

        content = content.strip()
        return json.loads(content)

    def _heuristic_fallback(
        self,
        raw_problem_input: str,
        intent: IntentClassificationOutput,
        error: Optional[Exception],
    ) -> PlanningOutput:
        """
        Deterministic conceptual fallback plan when LLM output cannot be used.

        Intentionally avoids code-like tokens to satisfy PlanningOutput
        validation.
        """
        # Very lightweight restatement that does not depend heavily on intent.
        problem_restated = (
            "Design a clear and efficient strategy to solve the described "
            "programming problem while balancing correctness and scalability."
        )

        assumptions = [
            "Input data can be parsed into a well defined internal representation.",
            "The available computing resources are within typical bounds for "
            "software engineering problems.",
        ]

        approach_a = SolutionApproach(
            id="baseline",
            name="Direct and straightforward approach",
            high_level_steps=[
                "Interpret the problem statement and identify the main operations.",
                "Use simple data structures to represent the input.",
                "Process the data in a clear and sequential manner.",
                "Return the result using the simplest correct procedure.",
            ],
            complexity_estimate={"time": "O(N * N)", "space": "O(1)"},
            pros=[
                "Easy to reason about and explain.",
                "Suitable for small input sizes and learning scenarios.",
            ],
            cons=[
                "May be inefficient for large inputs.",
                "Might not fully exploit structure in the data.",
            ],
            suitable_for=["small inputs", "teaching", "exploratory experiments"],
        )

        approach_b = SolutionApproach(
            id="optimized",
            name="Structure aware and performance oriented approach",
            high_level_steps=[
                "Analyze the input characteristics and constraints.",
                "Select data representations that reduce unnecessary work.",
                "Organize the computation to avoid repeated effort.",
                "Carefully account for boundary conditions and unusual cases.",
            ],
            complexity_estimate={"time": "O(N log N)", "space": "O(N)"},
            pros=[
                "Better performance for medium and large inputs.",
                "More robust in the presence of diverse edge cases.",
            ],
            cons=[
                "Requires more design effort and careful verification.",
                "Slightly harder to explain to less experienced engineers.",
            ],
            suitable_for=["production systems", "large inputs", "performance focus"],
        )

        justification = (
            "The structure aware and performance oriented approach offers a more "
            "balanced trade off between clarity and scalability. It requires more "
            "initial design work than the direct approach but is better aligned "
            "with long term maintenance and performance goals."
        )

        # Include minimal error context only in comments; PlanningOutput does not
        # carry an explicit raw_json field, so we avoid embedding technical data.
        _ = error  # kept for potential future logging by the caller if desired.

        return PlanningOutput(
            problem_restated=problem_restated,
            assumptions=assumptions,
            approaches=[approach_a, approach_b],
            selected_approach_id="optimized",
            selected_approach_justification=justification,
        )


def create_default_engineering_planner() -> EngineeringPlannerAgent:
    """
    Convenience factory that builds an EngineeringPlannerAgent using
    environment variables for configuration.

    Environment variables:
      - CODEPILOT_PLANNER_MODEL: override default model name.
    """
    model = os.getenv("CODEPILOT_PLANNER_MODEL", EngineeringPlannerConfig.model)
    config = EngineeringPlannerConfig(model=model)
    client = OpenAI()
    return EngineeringPlannerAgent(client=client, config=config)
