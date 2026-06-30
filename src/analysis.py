from __future__ import annotations

import time

from src.models import (
    AgentTrace,
    AnsweredQuestion,
    Finding,
    Severity,
)
from src.utils import DEFAULT_MODEL, get_anthropic_client, load_principles

SYSTEM_PROMPT = """You are the Analysis Agent for a data audit workflow. Your job is to evaluate the answered interview questions against a set of architectural principles.

For each principle, review all answers and identify:
1. Patterns that ALIGN with the principle (positive findings)
2. Patterns that VIOLATE the principle (negative findings — flag these)
3. Standard practices that don't strongly align or violate (skip these — don't create noise)

For each finding, provide:
- The principle it relates to
- Severity (high/medium/low/info)
- A clear observation
- Supporting evidence (quote or reference specific answers)
- A recommendation
- Whether it's a positive finding (affirming good practice) or negative (flagging a concern)

Be calibrated: not every answer maps to a finding. Only flag patterns that are clearly relevant to the principles. A finding should be actionable, not a restatement of the answer."""

FINDINGS_TOOL = {
    "name": "submit_findings",
    "description": "Submit analysis findings for the application",
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "principle_id": {"type": "string"},
                        "principle_name": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["high", "medium", "low", "info"],
                        },
                        "observation": {"type": "string"},
                        "evidence": {"type": "string"},
                        "recommendation": {"type": "string"},
                        "is_positive": {"type": "boolean"},
                    },
                    "required": [
                        "principle_id",
                        "principle_name",
                        "severity",
                        "observation",
                        "evidence",
                        "recommendation",
                        "is_positive",
                    ],
                },
            }
        },
        "required": ["findings"],
    },
}


def analyze_against_principles(
    answered_questions: list[AnsweredQuestion],
    application_name: str,
    principles_path=None,
) -> tuple[list[Finding], AgentTrace]:
    start = time.time()
    client = get_anthropic_client()

    principles = load_principles(principles_path)

    answers_text = "\n\n".join(
        f"[{a.question_id}] Q: {a.question_text}\n"
        f"A: {a.synthesized_answer}\n"
        f"Type: {a.answer_type.value} | Confidence: {a.confidence} | "
        f"Completeness: {a.completeness.value}"
        for a in answered_questions
    )

    principles_text = "\n\n".join(
        f"Principle: {p['name']} (ID: {p['id']})\n"
        f"Description: {p['description']}\n"
        f"Severity: {p['severity']}\n"
        f"Positive indicators: {', '.join(p['indicators']['positive'])}\n"
        f"Negative indicators: {', '.join(p['indicators']['negative'])}"
        for p in principles["principles"]
    )

    user_msg = (
        f"Application: {application_name}\n\n"
        f"ARCHITECTURAL PRINCIPLES:\n{principles_text}\n\n"
        f"ANSWERED QUESTIONS:\n{answers_text}\n\n"
        f"Evaluate the answers against the principles. Only create findings "
        f"for clear alignments or violations."
    )

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[FINDINGS_TOOL],
        tool_choice={"type": "tool", "name": "submit_findings"},
        messages=[{"role": "user", "content": user_msg}],
    )

    tool_input = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_findings":
            tool_input = block.input
            break

    if not tool_input:
        raise ValueError("Analysis agent did not return structured output")

    findings = [
        Finding(
            principle_id=f["principle_id"],
            principle_name=f["principle_name"],
            severity=Severity(f["severity"]),
            observation=f["observation"],
            evidence=f["evidence"],
            recommendation=f["recommendation"],
            is_positive=f["is_positive"],
        )
        for f in tool_input["findings"]
    ]

    duration = time.time() - start
    trace = AgentTrace(
        agent_name="analysis",
        phase="C",
        input_summary=f"{len(answered_questions)} answers for {application_name}",
        output_summary=f"{len(findings)} findings ({sum(1 for f in findings if not f.is_positive)} concerns, {sum(1 for f in findings if f.is_positive)} positive)",
        duration_seconds=round(duration, 2),
        llm_calls=1,
        tokens_used=response.usage.input_tokens + response.usage.output_tokens,
    )

    return findings, trace
