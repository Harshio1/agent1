from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI
from pydantic import ValidationError

from core.models import (
    IntentClassificationOutput,
    IntentConstraints,
    MemoryContext,
    ProblemContext,
    ProblemType,
    StyleMode,
    StylePreferences,
)


@dataclass
class IntentClassifierConfig:
    """
    Configuration for the LLM-backed IntentClassifierAgent.

    Attributes:
        model: Name of the chat completion model to use.
        max_retries: Number of attempts to obtain a valid, parseable response.
        temperature: Sampling temperature for the model.
    """

    model: str = "gpt-4.1-mini"
    max_retries: int = 2
    temperature: float = 0.0


class IntentClassifierAgent:
    """
    LLM-backed intent classifier.

    Responsibilities:
      - Consume only raw_problem_input and memory_context.
      - Produce a validated IntentClassificationOutput.
      - Enforce strict JSON-only responses and robustly handle malformed output.
    """

    def __init__(
        self,
        client: OpenAI,
        config: Optional[IntentClassifierConfig] = None,
    ) -> None:
        self._client = client
        self._config = config or IntentClassifierConfig()

    def classify(
        self,
        raw_problem_input: str,
        memory_context: Optional[MemoryContext],
    ) -> IntentClassificationOutput:
        """
        Classify the user's problem using the configured LLM.

        This method attempts multiple times to obtain a valid JSON object that
        conforms to IntentClassificationOutput. If validation repeatedly fails,
        a safe heuristic fallback is used.
        """
        context_hint = self._build_memory_hint(memory_context)

        last_error: Optional[Exception] = None
        for attempt in range(self._config.max_retries + 1):
            try:
                raw_json = self._invoke_llm(raw_problem_input, context_hint)
                parsed = IntentClassificationOutput.model_validate(raw_json)
                # Preserve the full raw JSON for traceability.
                parsed.raw_json = raw_json
                return parsed
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_error = exc
                # On retry, the prompt will be slightly different to emphasize format.
                continue

        # Fallback to heuristic classification if LLM output cannot be validated.
        return self._heuristic_fallback(raw_problem_input, memory_context, last_error)

    def _build_memory_hint(self, memory_context: Optional[MemoryContext]) -> str:
        if memory_context is None:
            return "No prior user preferences are available."

        language = memory_context.preferred_language or "unknown"
        style = (
            memory_context.preferred_style_mode.value
            if memory_context.preferred_style_mode
            else "unknown"
        )
        return (
            f"User preferred language: {language}. "
            f"User preferred style_mode: {style}."
        )

    def _invoke_llm(self, problem_input: str, memory_hint: str) -> dict[str, Any]:
        """
        Call the underlying LLM and return a parsed JSON object.

        Any JSON/validation issues are raised to the caller.
        """
        system_prompt = (
            "You are an intent classification engine for a software engineering "
            "assistant called CodePilot.\n\n"
            "Your ONLY job is to read the user's programming problem and output a "
            "STRICT JSON object matching this schema (no prose, no markdown):\n\n"
            "{\n"
            '  "problem_type": one of ["dsa", "system", "bug_fix", "optimization", "other"],\n'
            '  "context": one of ["interview", "production", "learning", "experimental", "unknown"],\n'
            '  "languages": [list of language names as lowercase strings],\n'
            '  "constraints": {\n'
            '    "time_complexity_target": string or null,\n'
            '    "space_complexity_target": string or null,\n'
            '    "memory_limit_mb": integer or null,\n'
            '    "time_budget_ms": integer or null,\n'
            '    "additional_constraints": [list of strings]\n'
            "  },\n"
            '  "style_preferences": {\n'
            '    "language": string or null,\n'
            '    "style_mode": one of ["readable", "competitive", "enterprise", null]\n'
            "  },\n"
            '  "confidence": number between 0 and 1\n'
            "}\n\n"
            "Output ONLY the JSON object. Do not include explanations, comments, or "
            "any text before or after the JSON."
        )

        user_prompt = (
            f"{memory_hint}\n\n"
            "User problem description:\n"
            f"{problem_input}\n"
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
            raise ValueError("LLM returned empty content for intent classification.")

        # The model is instructed to output pure JSON. We still defensively strip.
        content = content.strip()
        return json.loads(content)

    def _heuristic_fallback(
        self,
        raw_problem_input: str,
        memory_context: Optional[MemoryContext],
        error: Optional[Exception],
    ) -> IntentClassificationOutput:
        """
        Heuristic classification used only when the LLM path fails.
        """
        text = raw_problem_input.lower()

        if "optimize" in text or "optimization" in text:
            problem_type = ProblemType.OPTIMIZATION
        elif "bug" in text or "fix" in text:
            problem_type = ProblemType.BUG_FIX
        elif "system" in text or "api" in text:
            problem_type = ProblemType.SYSTEM
        else:
            problem_type = ProblemType.DSA

        if "interview" in text:
            context = ProblemContext.INTERVIEW
        elif "production" in text:
            context = ProblemContext.PRODUCTION
        else:
            context = ProblemContext.UNKNOWN

        preferred_style = (
            memory_context.preferred_style_mode
            if memory_context and memory_context.preferred_style_mode
            else StyleMode.READABLE
        )

        preferred_language = (
            memory_context.preferred_language
            if memory_context and memory_context.preferred_language
            else "python"
        )

        return IntentClassificationOutput(
            problem_type=problem_type,
            context=context,
            languages=[preferred_language],
            constraints=IntentConstraints(),
            style_preferences=StylePreferences(
                language=preferred_language,
                style_mode=preferred_style,
            ),
            confidence=0.4,
            raw_json={
                "fallback": True,
                "error": str(error) if error else None,
            },
        )


def create_default_intent_classifier() -> IntentClassifierAgent:
    """
    Convenience factory that builds an IntentClassifierAgent using environment
    variables for configuration.

    Environment variables:
      - CODEPILOT_INTENT_MODEL: override default model name.
    """
    model = os.getenv("CODEPILOT_INTENT_MODEL", IntentClassifierConfig.model)
    config = IntentClassifierConfig(model=model)
    client = OpenAI()
    return IntentClassifierAgent(client=client, config=config)

