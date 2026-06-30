from __future__ import annotations

import time

from src.models import (
    AgentTrace,
    AnsweredQuestion,
    AnswerType,
    Completeness,
    SourceCitation,
    SourceType,
)
from src.utils import DEFAULT_MODEL, get_anthropic_client

SYSTEM_PROMPT = """You are the Validation Agent for a data audit workflow. Your job is to cross-check synthesized answers for quality and consistency.

Review the set of answered questions and:
1. Check for INTERNAL CONFLICTS: does one answer contradict another? If the transcript says X but the debrief says Y, flag it.
2. Verify COMPLETENESS: are any answers marked as "fully_answered" but actually incomplete? Are "not_addressed" answers actually present in the source list?
3. Adjust CONFIDENCE SCORES: based on how well-supported each answer is. Multiple corroborating sources = higher confidence. Single uncorroborated claim = lower confidence.
4. Validate CLASSIFICATIONS: is a "factual" answer actually factual? Is something marked "anecdotal" actually documented fact?

Return the adjusted answers with any corrections. If an answer is fine, return it unchanged. Only modify answers that need correction."""

VALIDATION_TOOL = {
    "name": "submit_validated_answers",
    "description": "Submit validated and adjusted answers",
    "input_schema": {
        "type": "object",
        "properties": {
            "validated_answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {"type": "string"},
                        "confidence_adjusted": {"type": "integer", "minimum": 0, "maximum": 100},
                        "completeness_adjusted": {
                            "type": "string",
                            "enum": ["fully_answered", "partially_answered", "not_addressed"],
                        },
                        "answer_type_adjusted": {
                            "type": "string",
                            "enum": ["factual", "anecdotal", "mixed"],
                        },
                        "conflicts_found": {"type": ["string", "null"]},
                        "validation_notes": {"type": ["string", "null"]},
                        "answer_revised": {"type": ["string", "null"]},
                    },
                    "required": [
                        "question_id",
                        "confidence_adjusted",
                        "completeness_adjusted",
                        "answer_type_adjusted",
                    ],
                },
            }
        },
        "required": ["validated_answers"],
    },
}


def validate_answers(
    answered_questions: list[AnsweredQuestion],
    application_name: str,
) -> tuple[list[AnsweredQuestion], AgentTrace]:
    start = time.time()
    client = get_anthropic_client()

    answers_text = "\n\n".join(
        f"[{a.question_id}] Q: {a.question_text}\n"
        f"A: {a.synthesized_answer}\n"
        f"Type: {a.answer_type.value} | Confidence: {a.confidence} | "
        f"Completeness: {a.completeness.value}\n"
        f"Sources: {', '.join(f'{s.source_type.value}:{s.filename}' for s in a.sources)}\n"
        f"Conflicts: {a.conflicts or 'None'}"
        for a in answered_questions
    )

    user_msg = (
        f"Application: {application_name}\n\n"
        f"ANSWERED QUESTIONS TO VALIDATE:\n{answers_text}\n\n"
        f"Cross-check all answers. Flag conflicts, adjust confidence and completeness "
        f"where warranted, verify classifications."
    )

    # Chunk validation when many answers
    if len(answered_questions) > 15:
        all_validated = []
        total_tokens_used = 0
        mid = len(answered_questions) // 2
        for chunk in [answered_questions[:mid], answered_questions[mid:]]:
            chunk_text = "\n\n".join(
                f"[{a.question_id}] Q: {a.question_text}\n"
                f"A: {a.synthesized_answer}\n"
                f"Type: {a.answer_type.value} | Confidence: {a.confidence} | "
                f"Completeness: {a.completeness.value}\n"
                f"Sources: {', '.join(f'{s.source_type.value}:{s.filename}' for s in a.sources)}\n"
                f"Conflicts: {a.conflicts or 'None'}"
                for a in chunk
            )
            chunk_msg = (
                f"Application: {application_name}\n\n"
                f"ANSWERED QUESTIONS TO VALIDATE:\n{chunk_text}\n\n"
                f"Cross-check all answers. Flag conflicts, adjust confidence and "
                f"completeness where warranted, verify classifications."
            )
            resp = client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                tools=[VALIDATION_TOOL],
                tool_choice={"type": "tool", "name": "submit_validated_answers"},
                messages=[{"role": "user", "content": chunk_msg}],
            )
            total_tokens_used += resp.usage.input_tokens + resp.usage.output_tokens
            for block in resp.content:
                if block.type == "tool_use":
                    adj_map = {v["question_id"]: v for v in block.input.get("validated_answers", [])}
                    for a in chunk:
                        adj = adj_map.get(a.question_id)
                        if adj:
                            all_validated.append(a.model_copy(update={
                                "confidence": adj["confidence_adjusted"],
                                "completeness": Completeness(adj["completeness_adjusted"]),
                                "answer_type": AnswerType(adj["answer_type_adjusted"]),
                                "conflicts": adj.get("conflicts_found") or a.conflicts,
                                "synthesized_answer": adj.get("answer_revised") or a.synthesized_answer,
                            }))
                        else:
                            all_validated.append(a)
                    break
            else:
                all_validated.extend(chunk)

        adjustments_made = sum(
            1 for orig, val in zip(answered_questions, all_validated)
            if orig.confidence != val.confidence
            or orig.completeness != val.completeness
            or orig.answer_type != val.answer_type
        )
        duration = time.time() - start
        trace = AgentTrace(
            agent_name="validation",
            phase="C",
            input_summary=f"{len(answered_questions)} answers for {application_name}",
            output_summary=f"{adjustments_made} answers adjusted",
            duration_seconds=round(duration, 2),
            llm_calls=2,
            tokens_used=total_tokens_used,
        )
        return all_validated, trace

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[VALIDATION_TOOL],
        tool_choice={"type": "tool", "name": "submit_validated_answers"},
        messages=[{"role": "user", "content": user_msg}],
    )

    tool_input = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_validated_answers":
            tool_input = block.input
            break

    if not tool_input:
        stop = response.stop_reason
        block_types = [b.type for b in response.content]
        raise ValueError(
            f"Validation agent did not return structured output. "
            f"Stop reason: {stop}, blocks: {block_types}"
        )

    answer_map = {a.question_id: a for a in answered_questions}
    adjustments = {v["question_id"]: v for v in tool_input["validated_answers"]}

    validated = []
    for orig in answered_questions:
        adj = adjustments.get(orig.question_id)
        if adj:
            validated.append(
                orig.model_copy(
                    update={
                        "confidence": adj["confidence_adjusted"],
                        "completeness": Completeness(adj["completeness_adjusted"]),
                        "answer_type": AnswerType(adj["answer_type_adjusted"]),
                        "conflicts": adj.get("conflicts_found") or orig.conflicts,
                        "synthesized_answer": adj.get("answer_revised") or orig.synthesized_answer,
                    }
                )
            )
        else:
            validated.append(orig)

    adjustments_made = sum(
        1 for orig, val in zip(answered_questions, validated)
        if orig.confidence != val.confidence
        or orig.completeness != val.completeness
        or orig.answer_type != val.answer_type
    )

    duration = time.time() - start
    trace = AgentTrace(
        agent_name="validation",
        phase="C",
        input_summary=f"{len(answered_questions)} answers for {application_name}",
        output_summary=f"{adjustments_made} answers adjusted",
        duration_seconds=round(duration, 2),
        llm_calls=1,
        tokens_used=response.usage.input_tokens + response.usage.output_tokens,
    )

    return validated, trace
