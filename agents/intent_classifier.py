from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from groq import Groq
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
    """

    model: str = "llama3-8b-8192"
    max_retries: int = 2
    temperature: float = 0.0


class IntentClassifierAgent:
    """
    LLM-backed intent classifier using Groq.
    """

    def __init__(
        self,
        client: Groq,
        config: Optional[IntentClassifierConfig] = None,
    ) -> None:
        self._client = client
        self._config = config or IntentClassifierConfig()

    def classify(
        self,
        raw_problem_input: str,
        memory_context: Optional[MemoryContext],
    ) -> IntentClassificationOutput:
        context_hint = self._build_memory_hint(memory_context)

        last_error: Optional[Exception] = None
        for _ in range(self._config.max_retries + 1):
            try:
                raw_json = self._invoke_llm(raw_problem_input, context_hint)
                parsed = IntentClassificationOutput.model_validate(raw_json)
                parsed.raw_json = raw_json
                return parsed
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_error = exc
                continue

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
        system_prompt = (
            "You are an intent classification engine for a software engineering "
            "assistant called CodePilot.\n\n"
            "Output ONLY a strict JSON object matching this schema:\n\n"
            "{\n"
            '  "problem_type": one of ["dsa", "system", "bug_fix", "optimization", "other"],\n'
            '  "context": one of ["interview", "production", "learning", "experimental", "unknown"],\n'
            '  "languages": [list of lowercase language strings],\n'
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
            "Return ONLY valid JSON."
        )

        user_prompt = (
            f"{memory_hint}\n\n"
            "User problem description:\n"
            f"{problem_input}"
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
        if not content:
            raise ValueError("LLM returned empty content.")

        return json.loads(content.strip())

    def _heuristic_fallback(
        self,
        raw_problem_input: str,
        memory_context: Optional[MemoryContext],
        error: Optional[Exception],
    ) -> IntentClassificationOutput:
        text = raw_problem_input.lower()

        if "optimize" in text:
            problem_type = ProblemType.OPTIMIZATION
        elif "bug" in text or "fix" in text:
            problem_type = ProblemType.BUG_FIX
        elif "system" in text or "api" in text:
            problem_type = ProblemType.SYSTEM
        else:
            problem_type = ProblemType.DSA

        context = (
            ProblemContext.INTERVIEW
            if "interview" in text
            else ProblemContext.PRODUCTION
            if "production" in text
            else ProblemContext.UNKNOWN
        )

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
            raw_json={"fallback": True, "error": str(error)},
        )


def create_default_intent_classifier() -> IntentClassifierAgent:
    model = os.getenv("CODEPILOT_INTENT_MODEL", "llama3-8b-8192")
    config = IntentClassifierConfig(model=model)

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return IntentClassifierAgent(client=client, config=config)
