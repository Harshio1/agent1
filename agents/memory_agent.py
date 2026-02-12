from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from ..core.models import (
    DebugOutput,
    IntentClassificationOutput,
    MemoryContext,
    StyleMode,
    TestingOutput,
)


@dataclass
class MemoryAgentConfig:
    """
    Configuration for the LLM-backed MemoryAgent.

    Attributes:
        model: Name of the chat completion model to use for pattern extraction.
        max_retries: Number of attempts to obtain a valid, parseable response.
        temperature: Sampling temperature for the model.
    """

    model: str = "gpt-4.1-mini"
    max_retries: int = 2
    temperature: float = 0.1


class _MemoryUpdate(BaseModel):
    """
    Internal helper model for validating LLM-generated memory updates.

    This represents structured insights extracted from execution outputs.
    """

    preferred_language: Optional[str] = None
    preferred_style_mode: Optional[str] = None
    recurring_weaknesses: List[str] = []
    mistake_categories: List[str] = []
    mistake_descriptions: List[str] = []
    interaction_summary: Optional[str] = None


class MemoryAgent:
    """
    LLM-backed memory agent that extracts user preferences and recurring
    weaknesses from execution outputs.

    Responsibilities:
      - Analyze IntentClassificationOutput, TestingOutput, and DebugOutput
        to infer user preferences (language, style).
      - Identify recurring weakness patterns from test failures and debug
        analyses.
      - Produce structured updates that can be persisted via MemoryStorage.

    This agent is designed to be deterministic and safe to call multiple times
    with the same inputs.
    """

    def __init__(
        self,
        client: OpenAI,
        config: Optional[MemoryAgentConfig] = None,
    ) -> None:
        self._client = client
        self._config = config or MemoryAgentConfig()

    def extract_updates(
        self,
        intent: Optional[IntentClassificationOutput],
        testing: Optional[TestingOutput],
        debug: Optional[DebugOutput],
        existing_context: Optional[MemoryContext],
    ) -> Dict[str, Any]:
        """
        Extract structured memory updates from execution outputs.

        Returns a dictionary with keys:
          - preferred_language: Optional[str]
          - preferred_style_mode: Optional[StyleMode]
          - mistakes: List[Dict[str, str]] with 'category' and 'description'
          - interaction_summary: Optional[str]

        If LLM extraction fails, falls back to deterministic heuristics based
        on the provided outputs.
        """
        if not intent and not testing and not debug:
            # No execution data to analyze; return empty updates.
            return {
                "preferred_language": None,
                "preferred_style_mode": None,
                "mistakes": [],
                "interaction_summary": None,
            }

        last_error: Optional[Exception] = None
        update: Optional[_MemoryUpdate] = None

        for _attempt in range(self._config.max_retries + 1):
            try:
                raw_json = self._invoke_llm(
                    intent=intent,
                    testing=testing,
                    debug=debug,
                    existing_context=existing_context,
                )
                update = _MemoryUpdate.model_validate(raw_json)
                break
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_error = exc
                continue

        if update is None:
            # Fallback to deterministic heuristics.
            update = self._heuristic_extraction(
                intent=intent,
                testing=testing,
                debug=debug,
                existing_context=existing_context,
                error=last_error,
            )

        # Convert to the format expected by orchestration.
        preferred_style_mode: Optional[StyleMode] = None
        if update.preferred_style_mode:
            try:
                preferred_style_mode = StyleMode(update.preferred_style_mode.lower())
            except ValueError:
                preferred_style_mode = None

        mistakes: List[Dict[str, str]] = []
        for category, description in zip(
            update.mistake_categories,
            update.mistake_descriptions,
        ):
            if category and description:
                mistakes.append({"category": category, "description": description})

        return {
            "preferred_language": (
                update.preferred_language.lower().strip()
                if update.preferred_language
                else None
            ),
            "preferred_style_mode": preferred_style_mode,
            "mistakes": mistakes,
            "interaction_summary": update.interaction_summary,
        }

    def _invoke_llm(
        self,
        intent: Optional[IntentClassificationOutput],
        testing: Optional[TestingOutput],
        debug: Optional[DebugOutput],
        existing_context: Optional[MemoryContext],
    ) -> Dict[str, Any]:
        """
        Call the LLM to extract memory updates from execution outputs.

        The LLM is asked to infer user preferences and recurring weaknesses
        based on observed behavior patterns.
        """
        system_prompt = (
            "You are the memory component of a software engineering agent called "
            "CodePilot.\n\n"
            "Your task is to analyze execution outputs and extract:\n"
            "1. User preferences (preferred programming language, code style mode)\n"
            "2. Recurring weaknesses (mistake categories and descriptions)\n"
            "3. A brief interaction summary\n\n"
            "You MUST respond with a STRICT JSON object matching this schema:\n\n"
            "{\n"
            '  \"preferred_language\": string or null (e.g., \"python\"),\n'
            '  \"preferred_style_mode\": one of [\"readable\", \"competitive\", \"enterprise\"] or null,\n'
            '  \"recurring_weaknesses\": [list of high-level weakness categories],\n'
            '  \"mistake_categories\": [list of specific mistake category strings],\n'
            '  \"mistake_descriptions\": [list of mistake description strings, same length as categories],\n'
            '  \"interaction_summary\": string or null (brief summary of this interaction)\n'
            "}\n\n"
            "Guidelines:\n"
            "- Infer preferences from observed choices (e.g., if intent shows Python, "
            "prefer Python).\n"
            "- Extract weaknesses from test failures and debug root causes.\n"
            "- Group similar mistakes into recurring_weaknesses.\n"
            "- Keep interaction_summary concise (1-2 sentences).\n"
            "- Do NOT include markdown, comments, or text outside the JSON.\n"
        )

        execution_summary = self._build_execution_summary(
            intent=intent,
            testing=testing,
            debug=debug,
            existing_context=existing_context,
        )

        user_prompt = (
            "Execution outputs to analyze:\n"
            f"{json.dumps(execution_summary, ensure_ascii=False, indent=2)}\n\n"
            "Extract user preferences and recurring weaknesses from this data."
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
            raise ValueError("LLM returned empty content for memory extraction.")

        content = content.strip()
        return json.loads(content)

    def _build_execution_summary(
        self,
        intent: Optional[IntentClassificationOutput],
        testing: Optional[TestingOutput],
        debug: Optional[DebugOutput],
        existing_context: Optional[MemoryContext],
    ) -> Dict[str, Any]:
        """
        Build a compact, structured summary of execution outputs for LLM analysis.
        """
        summary: Dict[str, Any] = {}

        if intent:
            summary["intent"] = {
                "problem_type": intent.problem_type.value,
                "context": intent.context.value,
                "languages": intent.languages,
                "style_preferences": {
                    "language": intent.style_preferences.language,
                    "style_mode": (
                        intent.style_preferences.style_mode.value
                        if intent.style_preferences.style_mode
                        else None
                    ),
                },
            }

        if testing:
            summary["testing"] = {
                "total_tests": len(testing.test_cases),
                "passed": len(testing.passed_cases),
                "failed": len(testing.failed_cases),
                "overall_status": testing.overall_status.value,
                "failure_types": [
                    f.failure_type.value for f in testing.failures
                ],
            }

        if debug and debug.root_causes:
            summary["debug"] = {
                "root_cause_count": len(debug.root_causes),
                "root_causes": [
                    {
                        "description": rc.description,
                        "failed_assumptions": rc.failed_assumptions,
                        "impacted_test_count": len(rc.impacted_test_case_ids),
                    }
                    for rc in debug.root_causes
                ],
                "selected_fix_id": debug.selected_fix_id,
            }

        if existing_context:
            summary["existing_memory"] = {
                "preferred_language": existing_context.preferred_language,
                "preferred_style_mode": (
                    existing_context.preferred_style_mode.value
                    if existing_context.preferred_style_mode
                    else None
                ),
                "repeated_weaknesses": existing_context.repeated_weaknesses,
            }

        return summary

    def _heuristic_extraction(
        self,
        intent: Optional[IntentClassificationOutput],
        testing: Optional[TestingOutput],
        debug: Optional[DebugOutput],
        existing_context: Optional[MemoryContext],
        error: Optional[Exception],
    ) -> _MemoryUpdate:
        """
        Deterministic fallback extraction when LLM analysis fails.

        Uses simple heuristics to extract preferences and mistakes from the
        provided outputs.
        """
        _ = error  # Reserved for potential logging.

        preferred_language: Optional[str] = None
        preferred_style_mode: Optional[str] = None

        if intent:
            if intent.style_preferences.language:
                preferred_language = intent.style_preferences.language.lower()
            elif intent.languages:
                preferred_language = intent.languages[0].lower() if intent.languages else None

            if intent.style_preferences.style_mode:
                preferred_style_mode = intent.style_preferences.style_mode.value

        # If no preference from intent, preserve existing context.
        if not preferred_language and existing_context and existing_context.preferred_language:
            preferred_language = existing_context.preferred_language
        if not preferred_style_mode and existing_context and existing_context.preferred_style_mode:
            preferred_style_mode = existing_context.preferred_style_mode.value

        mistake_categories: List[str] = []
        mistake_descriptions: List[str] = []
        recurring_weaknesses: List[str] = []

        if debug and debug.root_causes:
            for rc in debug.root_causes:
                category = (
                    rc.failed_assumptions[0]
                    if rc.failed_assumptions
                    else "general_bug"
                )
                mistake_categories.append(category)
                mistake_descriptions.append(rc.description)
                # Infer weakness category from description keywords.
                desc_lower = rc.description.lower()
                if "timeout" in desc_lower or "performance" in desc_lower:
                    if "performance" not in recurring_weaknesses:
                        recurring_weaknesses.append("performance")
                elif "memory" in desc_lower or "resource" in desc_lower:
                    if "resource_management" not in recurring_weaknesses:
                        recurring_weaknesses.append("resource_management")
                elif "edge" in desc_lower or "boundary" in desc_lower:
                    if "edge_case_handling" not in recurring_weaknesses:
                        recurring_weaknesses.append("edge_case_handling")
                else:
                    if "logic_error" not in recurring_weaknesses:
                        recurring_weaknesses.append("logic_error")

        interaction_summary: Optional[str] = None
        if intent and testing:
            status = testing.overall_status.value
            problem_type = intent.problem_type.value
            interaction_summary = (
                f"Solved a {problem_type} problem. Tests: {status}. "
                f"{len(testing.passed_cases)}/{len(testing.test_cases)} passed."
            )

        return _MemoryUpdate(
            preferred_language=preferred_language,
            preferred_style_mode=preferred_style_mode,
            recurring_weaknesses=recurring_weaknesses,
            mistake_categories=mistake_categories,
            mistake_descriptions=mistake_descriptions,
            interaction_summary=interaction_summary,
        )


def create_default_memory_agent() -> MemoryAgent:
    """
    Convenience factory that builds a MemoryAgent using environment variables
    for configuration.

    Environment variables:
      - CODEPILOT_MEMORY_MODEL: override default model name.
    """
    model = os.getenv("CODEPILOT_MEMORY_MODEL", MemoryAgentConfig.model)
    config = MemoryAgentConfig(model=model)
    client = OpenAI()
    return MemoryAgent(client=client, config=config)
