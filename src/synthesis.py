from __future__ import annotations

import time

from src.models import (
    AgentTrace,
    AIObservation,
    AppResult,
    Completeness,
    CoverageCell,
    EngagementResult,
    QuestionFramework,
)
from src.utils import DEFAULT_MODEL, get_anthropic_client

SUMMARY_SYSTEM_PROMPT = """You are the Synthesis Agent for a data audit workflow. Generate an executive summary of the engagement findings.

The summary should cover:
1. Engagement overview (applications reviewed, interview count)
2. Overall completeness (what percentage of questions were fully answered)
3. Key findings across all applications
4. Major gaps and areas needing follow-up
5. Cross-application patterns (data flows, shared dependencies, common pain points)

Keep the summary professional, concise, and deliverable-ready. This goes directly to the client."""

OBSERVATIONS_SYSTEM_PROMPT = """You are the Synthesis Agent making a free-form observations pass. You've already processed structured answers for all interview questions. Now look across ALL raw data and surface patterns, risks, trends, or data points that NO question explicitly asked about.

Think like a good consultant who notices things they weren't asked about:
- Organizational dynamics that affect data flow
- Unstated assumptions or tribal knowledge
- Risks that span multiple applications
- Opportunities for consolidation or simplification
- Data governance gaps that emerged organically

For each observation, provide:
- The observation itself
- Supporting evidence (with source references)
- Which interviews surfaced this
- A suggested follow-up question for future interviews"""

SUMMARY_TOOL = {
    "name": "submit_summary",
    "description": "Submit the engagement summary",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
        },
        "required": ["summary"],
    },
}

OBSERVATIONS_TOOL = {
    "name": "submit_observations",
    "description": "Submit free-form AI observations",
    "input_schema": {
        "type": "object",
        "properties": {
            "observations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "observation": {"type": "string"},
                        "evidence": {"type": "string"},
                        "source_interviews": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "suggested_followup": {"type": ["string", "null"]},
                    },
                    "required": ["observation", "evidence", "source_interviews"],
                },
            }
        },
        "required": ["observations"],
    },
}


def build_coverage_matrix(
    framework: QuestionFramework,
    app_results: list[AppResult],
) -> list[CoverageCell]:
    cells = []
    for result in app_results:
        answer_map = {a.question_id: a for a in result.answered_questions}
        for q in framework.questions:
            answer = answer_map.get(q.id)
            cells.append(
                CoverageCell(
                    question_id=q.id,
                    application_name=result.application_name,
                    completeness=answer.completeness if answer else Completeness.NOT_ADDRESSED,
                )
            )
    return cells


def synthesize_engagement(
    framework: QuestionFramework,
    app_results: list[AppResult],
) -> tuple[EngagementResult, AgentTrace]:
    start = time.time()
    client = get_anthropic_client()
    total_tokens = 0

    coverage = build_coverage_matrix(framework, app_results)

    # --- Summary generation ---
    results_text = _format_results_for_summary(framework, app_results, coverage)

    summary_response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=2048,
        system=SUMMARY_SYSTEM_PROMPT,
        tools=[SUMMARY_TOOL],
        tool_choice={"type": "tool", "name": "submit_summary"},
        messages=[{"role": "user", "content": results_text}],
    )

    summary = ""
    for block in summary_response.content:
        if block.type == "tool_use":
            tool_data = block.input
            if "summary" in tool_data:
                summary = tool_data["summary"]
            else:
                summary = str(tool_data)
            break
        elif block.type == "text":
            summary = block.text

    total_tokens += summary_response.usage.input_tokens + summary_response.usage.output_tokens

    # --- AI Observations pass ---
    all_answers_text = _format_all_answers(app_results)

    obs_response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        system=OBSERVATIONS_SYSTEM_PROMPT,
        tools=[OBSERVATIONS_TOOL],
        tool_choice={"type": "tool", "name": "submit_observations"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Engagement: {framework.engagement_name}\n\n"
                    f"ALL ANSWERED QUESTIONS ACROSS APPLICATIONS:\n{all_answers_text}\n\n"
                    f"Surface patterns, risks, and observations beyond the explicit questions."
                ),
            }
        ],
    )

    observations = []
    for block in obs_response.content:
        if block.type == "tool_use":
            obs_list = block.input.get("observations", [])
            for o in obs_list:
                observations.append(
                    AIObservation(
                        observation=o.get("observation", ""),
                        evidence=o.get("evidence", ""),
                        source_interviews=o.get("source_interviews", []),
                        suggested_followup=o.get("suggested_followup"),
                    )
                )
            break

    total_tokens += obs_response.usage.input_tokens + obs_response.usage.output_tokens

    result = EngagementResult(
        engagement_name=framework.engagement_name,
        question_framework=framework,
        app_results=app_results,
        coverage_matrix=coverage,
        ai_observations=observations,
        summary=summary,
    )

    duration = time.time() - start
    trace = AgentTrace(
        agent_name="synthesis",
        phase="D",
        input_summary=f"{len(app_results)} applications, {len(framework.questions)} questions",
        output_summary=f"Summary + {len(observations)} AI observations + coverage matrix",
        duration_seconds=round(duration, 2),
        llm_calls=2,
        tokens_used=total_tokens,
    )

    return result, trace


def _format_results_for_summary(
    framework: QuestionFramework,
    app_results: list[AppResult],
    coverage: list[CoverageCell],
) -> str:
    total_cells = len(coverage)
    full = sum(1 for c in coverage if c.completeness == Completeness.FULL)
    partial = sum(1 for c in coverage if c.completeness == Completeness.PARTIAL)
    not_addressed = sum(1 for c in coverage if c.completeness == Completeness.NOT_ADDRESSED)

    lines = [
        f"Engagement: {framework.engagement_name}",
        f"Applications reviewed: {len(app_results)}",
        f"Total questions: {len(framework.questions)}",
        f"Coverage: {full}/{total_cells} fully answered, "
        f"{partial}/{total_cells} partial, "
        f"{not_addressed}/{total_cells} not addressed",
        "",
    ]

    for result in app_results:
        lines.append(f"\n--- {result.application_name} ---")
        lines.append(f"Interviewees: {', '.join(result.interviewees) or 'N/A'}")
        lines.append(f"Findings: {len(result.findings)}")

        for a in result.answered_questions:
            lines.append(
                f"  [{a.question_id}] {a.completeness.value} | "
                f"{a.answer_type.value} | confidence={a.confidence}"
            )
            if a.conflicts:
                lines.append(f"    CONFLICT: {a.conflicts}")

    return "\n".join(lines)


def _format_all_answers(app_results: list[AppResult]) -> str:
    lines = []
    for result in app_results:
        lines.append(f"\n=== {result.application_name} ===")
        for a in result.answered_questions:
            lines.append(
                f"[{a.question_id}] {a.question_text}\n"
                f"Answer: {a.synthesized_answer}\n"
                f"Type: {a.answer_type.value} | Confidence: {a.confidence}\n"
            )
    return "\n".join(lines)
