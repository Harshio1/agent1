from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from openai import OpenAI
from pydantic import ValidationError

from core.models import (
    CodeOutput,
    DebugOutput,
    IntentClassificationOutput,
    PlanningOutput,
    StyleMode,
)


@dataclass
class CoderConfig:
    """
    Configuration for the LLM-backed CoderAgent.

    Attributes:
        model: Name of the chat completion model to use.
        max_retries: Number of attempts to obtain a valid, parseable response.
        temperature: Sampling temperature for the model.
    """

    model: str
    max_retries: int = 2
    temperature: float = 0.1


class CoderAgent:
    """
    LLM-backed code generation agent.

    Responsibilities:
      - Generate Python code strictly according to the selected planning approach,
        style preferences, and (optionally) a single selected fix from debugging.
      - Never re-plan or invent new approaches.
      - Produce a CodeOutput instance via strict JSON-only LLM output.
    """

    def __init__(self, client: OpenAI, config: CoderConfig) -> None:
        self._client = client
        self._config = config

    def code(
        self,
        planning: PlanningOutput,
        intent: Optional[IntentClassificationOutput],
        debug: Optional[DebugOutput],
    ) -> CodeOutput:
        """
        Generate or update code based on the provided planning and optional
        debugging feedback.

        Retries on JSON/validation failures. If all retries fail, falls back to
        a deterministic minimal Python implementation that adheres to the
        planning intent at a high level.
        """
        style_mode = self._resolve_style_mode(intent)
        language_pref = self._resolve_language(intent)
        fix_context = self._extract_selected_fix(debug)

        last_error: Optional[Exception] = None
        for _attempt in range(self._config.max_retries + 1):
            try:
                raw_json = self._invoke_llm(
                    planning=planning,
                    style_mode=style_mode,
                    language_pref=language_pref,
                    fix_context=fix_context,
                )
                code_output = CodeOutput.model_validate(raw_json)
                # Extra safety: enforce language is python and at least one file.
                if code_output.language != "python":
                    raise ValueError("CoderAgent must produce language='python'.")
                if not code_output.source_files:
                    raise ValueError("CoderAgent must produce at least one source file.")
                return code_output
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError, ValueError) as exc:
                last_error = exc
                continue

        # Fallback: deterministic minimal implementation that satisfies the
        # CodeOutput schema and honors planning intent conceptually.
        return self._fallback_code(planning, style_mode, language_pref, last_error)

    def _resolve_style_mode(
        self,
        intent: Optional[IntentClassificationOutput],
    ) -> StyleMode:
        if intent and intent.style_preferences and intent.style_preferences.style_mode:
            return intent.style_preferences.style_mode
        return StyleMode.READABLE

    def _resolve_language(
        self,
        intent: Optional[IntentClassificationOutput],
    ) -> str:
        if intent and intent.style_preferences and intent.style_preferences.language:
            return intent.style_preferences.language.lower()
        return "python"

    def _extract_selected_fix(
        self,
        debug: Optional[DebugOutput],
    ) -> Optional[Dict[str, Any]]:
        """
        Extract the selected fix, if any, as a small structured context object.

        The agent must apply only the selected fix conceptually and avoid
        modifying unrelated logic.
        """
        if not debug or not debug.selected_fix_id:
            return None

        selected = None
        for fix in debug.proposed_fixes:
            if fix.id == debug.selected_fix_id:
                selected = fix
                break

        if selected is None:
            return None

        return {
            "id": selected.id,
            "target_root_cause_ids": selected.target_root_cause_ids,
            "description": selected.description,
            "notes_for_coder": selected.notes_for_coder,
        }

    def _invoke_llm(
        self,
        planning: PlanningOutput,
        style_mode: StyleMode,
        language_pref: str,
        fix_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Call the underlying LLM and return a parsed JSON object that should
        validate as CodeOutput.
        """
        system_prompt = (
            "You are the coding component of a software engineering agent called "
            "CodePilot.\n\n"
            "Your ONLY task is to generate Python source code strictly according "
            "to an existing engineering plan and, optionally, a single selected "
            "fix proposal. You must NOT change the high level approach.\n\n"
            "You MUST respond with a STRICT JSON object matching this schema:\n\n"
            "{\n"
            '  \"language\": \"python\",\n'
            '  \"style_mode\": one of [\"readable\", \"competitive\", \"enterprise\"],\n'
            '  \"source_files\": {\n'
            '    \"relative_path.py\": \"full file contents as a string\",\n'
            "    ... at least one file ...\n"
            "  },\n"
            '  \"entrypoint\": \"module.function_name\",\n'
            '  \"notes_for_tester\": [list of short strings]\n'
            "}\n\n"
            "Strict requirements:\n"
            "- language must be exactly \"python\".\n"
            "- entrypoint must refer to a function that is defined and callable "
            "in the generated code.\n"
            "- Do NOT include markdown, comments outside the code strings, or any "
            "text before or after the JSON.\n"
            "- Do NOT restate the plan or provide explanations; only JSON.\n"
        )

        planning_summary = {
            "selected_approach_id": planning.selected_approach_id,
            "approaches": [
                {
                    "id": a.id,
                    "name": a.name,
                    "high_level_steps": a.high_level_steps,
                    "complexity_estimate": a.complexity_estimate,
                }
                for a in planning.approaches
            ],
        }

        user_payload: Dict[str, Any] = {
            "planning": planning_summary,
            "style_preferences": {
                "language": language_pref,
                "style_mode": style_mode.value,
            },
        }
        if fix_context is not None:
            user_payload["selected_fix"] = fix_context

        user_prompt = json.dumps(user_payload, ensure_ascii=False)

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
            raise ValueError("LLM returned empty content for code generation.")

        content = content.strip()
        return json.loads(content)

    def _fallback_code(
        self,
        planning: PlanningOutput,
        style_mode: StyleMode,
        language_pref: str,
        error: Optional[Exception],
    ) -> CodeOutput:
        """
        Deterministic minimal Python implementation used when LLM output cannot
        be validated.

        This implementation does not attempt to fully realize the plan, but it
        respects the required schema and entrypoint contract.
        """
        _ = planning  # Currently unused but reserved for future heuristics.
        _ = language_pref
        _ = error

        source = (
            "def solve(input_data):\n"
            "    \"\"\"Fallback solution.\n"
            "\n"
            "    This implementation is a minimal placeholder used when automated\n"
            "    code generation is unavailable. It simply returns the input\n"
            "    unchanged so that the pipeline remains executable.\n"
            "    \"\"\"\n"
            "    return input_data\n"
        )

        return CodeOutput(
            language="python",
            style_mode=style_mode,
            source_files={"solution.py": source},
            entrypoint="solution.solve",
            notes_for_tester=[
                "This code was generated by a deterministic fallback path.",
                "It echoes the input and does not fully implement the intended plan.",
            ],
        )


def create_default_coder() -> CoderAgent:
    """
    Convenience factory that builds a CoderAgent using environment variables
    for configuration.

    Environment variables:
      - CODEPILOT_CODER_MODEL: override default model name.
    """
    model = os.getenv("CODEPILOT_CODER_MODEL", "gpt-4.1-mini")
    config = CoderConfig(model=model)
    client = OpenAI()
    return CoderAgent(client=client, config=config)

