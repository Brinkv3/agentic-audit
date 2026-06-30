from __future__ import annotations

import time

from src.models import (
    AgentTrace,
    AnsweredQuestion,
    AnswerType,
    Completeness,
    InterviewInputs,
    QuestionFramework,
    SourceCitation,
    SourceType,
)
from src.utils import count_tokens, get_llm_client

SYSTEM_PROMPT = """You are the Answer Agent for a data audit workflow. Your job is to answer interview questions as completely and accurately as possible by searching across ALL provided interview artifacts.

For EACH question, you must:
1. Search across all source documents (transcript, interviewer notes, BA notes, debrief, client docs)
2. Synthesize the most complete answer possible from all sources
3. Classify the answer type:
   - "factual": grounded in documented process, rule, or verifiable system behavior
     Examples: "Our pipeline runs nightly via Airflow", "Workday is our system of record"
   - "anecdotal": opinion, interpretation, single-person perspective, unverified claim
     Examples: "I think we pull from the lakehouse", "That process might have changed"
   - "mixed": some parts factual, some anecdotal — split and classify each part
4. Score confidence (0-100): how well-supported is this answer across inputs
5. Assess completeness: "fully_answered", "partially_answered", or "not_addressed"
6. Cite specific sources with excerpts
7. Flag any conflicts between sources

Key rules:
- If a question wasn't addressed in ANY source, mark it "not_addressed" with confidence 0
- If sources disagree, flag the conflict and present both perspectives
- Never invent information. Only synthesize from what's in the documents.
- Distinguish between "the person said X" (anecdotal) and "the documentation shows X" (factual)"""

ANSWER_TOOL = {
    "name": "submit_answers",
    "description": "Submit synthesized answers for all questions",
    "input_schema": {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {"type": "string"},
                        "synthesized_answer": {"type": "string"},
                        "answer_type": {
                            "type": "string",
                            "enum": ["factual", "anecdotal", "mixed"],
                        },
                        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                        "completeness": {
                            "type": "string",
                            "enum": ["fully_answered", "partially_answered", "not_addressed"],
                        },
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source_type": {"type": "string"},
                                    "filename": {"type": "string"},
                                    "excerpt": {"type": "string"},
                                },
                                "required": ["source_type", "filename", "excerpt"],
                            },
                        },
                        "conflicts": {"type": ["string", "null"]},
                    },
                    "required": [
                        "question_id",
                        "synthesized_answer",
                        "answer_type",
                        "confidence",
                        "completeness",
                        "sources",
                    ],
                },
            }
        },
        "required": ["answers"],
    },
}


def _build_source_context(inputs: InterviewInputs) -> str:
    sections = []
    for doc in inputs.documents:
        sections.append(
            f"=== SOURCE: {doc.filename} (type: {doc.source_type.value}) ===\n"
            f"{doc.content}"
        )
    return "\n\n".join(sections)


def _build_question_list(framework: QuestionFramework) -> str:
    lines = []
    for q in framework.questions:
        line = f"- [{q.id}] ({q.category}) {q.text}"
        if q.context:
            line += f"\n  Context: {q.context}"
        lines.append(line)
    return "\n".join(lines)


def synthesize_answers(
    framework: QuestionFramework,
    inputs: InterviewInputs,
) -> tuple[list[AnsweredQuestion], AgentTrace]:
    start = time.time()
    client = get_llm_client()

    source_context = _build_source_context(inputs)
    question_list = _build_question_list(framework)
    total_input_tokens = count_tokens(source_context + question_list)

    user_msg = (
        f"Application: {inputs.application_name}\n\n"
        f"INTERVIEW QUESTIONS:\n{question_list}\n\n"
        f"INTERVIEW ARTIFACTS:\n{source_context}\n\n"
        f"Answer every question listed above. Search across ALL source documents. "
        f"For questions not addressed in any source, mark as not_addressed."
    )

    # Chunk by category when many questions or large input
    if len(framework.questions) > 15 or total_input_tokens > 100_000:
        return _synthesize_chunked(framework, inputs, client, start)

    response = client.complete_with_tools(
        messages=[{"role": "user", "content": user_msg}],
        tools=[ANSWER_TOOL],
        system=SYSTEM_PROMPT,
        max_tokens=16384,
        tool_choice={"type": "tool", "name": "submit_answers"},
    )

    return _parse_response(response, framework, inputs, start, 1)


def _synthesize_chunked(
    framework: QuestionFramework,
    inputs: InterviewInputs,
    client,
    start: float,
) -> tuple[list[AnsweredQuestion], AgentTrace]:
    categories = {}
    for q in framework.questions:
        categories.setdefault(q.category, []).append(q)

    all_answered: list[AnsweredQuestion] = []
    total_tokens = 0
    llm_calls = 0
    source_context = _build_source_context(inputs)

    for category, questions in categories.items():
        chunk_questions = "\n".join(
            f"- [{q.id}] {q.text}" for q in questions
        )

        user_msg = (
            f"Application: {inputs.application_name}\n\n"
            f"QUESTIONS (category: {category}):\n{chunk_questions}\n\n"
            f"INTERVIEW ARTIFACTS:\n{source_context}\n\n"
            f"Answer these questions. Search across ALL source documents."
        )

        response = client.complete_with_tools(
            messages=[{"role": "user", "content": user_msg}],
            tools=[ANSWER_TOOL],
            system=SYSTEM_PROMPT,
            max_tokens=8192,
            tool_choice={"type": "tool", "name": "submit_answers"},
        )

        answered, _ = _parse_response(response, framework, inputs, start, 1)
        all_answered.extend(answered)
        total_tokens += response.usage.input_tokens + response.usage.output_tokens
        llm_calls += 1

    duration = time.time() - start
    trace = AgentTrace(
        agent_name="answer",
        phase="C",
        input_summary=(
            f"{len(framework.questions)} questions, "
            f"{len(inputs.documents)} sources for {inputs.application_name}"
        ),
        output_summary=f"{len(all_answered)} answers synthesized (chunked)",
        duration_seconds=round(duration, 2),
        llm_calls=llm_calls,
        tokens_used=total_tokens,
    )

    return all_answered, trace


def _parse_response(
    response,
    framework: QuestionFramework,
    inputs: InterviewInputs,
    start: float,
    llm_calls: int,
) -> tuple[list[AnsweredQuestion], AgentTrace]:
    if not response.tool_calls:
        raise ValueError(
            f"Answer agent did not return structured output. "
            f"Stop reason: {response.stop_reason}"
        )

    tool_input = response.tool_calls[0].arguments

    def _safe_source_type(raw: str) -> SourceType:
        try:
            return SourceType(raw)
        except ValueError:
            from src.utils import guess_source_type
            return SourceType(guess_source_type(raw))

    answered = []
    for a in tool_input["answers"]:
        sources = []
        for s in a.get("sources", []):
            try:
                sources.append(
                    SourceCitation(
                        source_type=_safe_source_type(s.get("source_type", "")),
                        filename=s.get("filename", "unknown"),
                        excerpt=s.get("excerpt", ""),
                    )
                )
            except (ValueError, KeyError):
                pass

        conflicts_raw = a.get("conflicts")
        if isinstance(conflicts_raw, dict):
            conflicts_raw = "; ".join(f"{k}: {v}" for k, v in conflicts_raw.items())
        elif conflicts_raw and not isinstance(conflicts_raw, str):
            conflicts_raw = str(conflicts_raw)

        answered.append(
            AnsweredQuestion(
                question_id=a["question_id"],
                question_text=next(
                    (q.text for q in framework.questions if q.id == a["question_id"]),
                    "",
                ),
                synthesized_answer=a["synthesized_answer"],
                answer_type=AnswerType(a["answer_type"]),
                confidence=int(a["confidence"]),
                completeness=Completeness(a["completeness"]),
                sources=sources,
                conflicts=conflicts_raw,
            )
        )

    duration = time.time() - start
    trace = AgentTrace(
        agent_name="answer",
        phase="C",
        input_summary=(
            f"{len(framework.questions)} questions, "
            f"{len(inputs.documents)} sources for {inputs.application_name}"
        ),
        output_summary=f"{len(answered)} answers synthesized",
        duration_seconds=round(duration, 2),
        llm_calls=llm_calls,
        tokens_used=response.usage.input_tokens + response.usage.output_tokens,
    )

    return answered, trace
