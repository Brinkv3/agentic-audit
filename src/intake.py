from __future__ import annotations

import time
from pathlib import Path

from src.models import (
    AgentTrace,
    InputDocument,
    InterviewInputs,
    SourceType,
)
from src.utils import count_tokens, get_llm_client, guess_source_type, parse_file

METADATA_SYSTEM_PROMPT = """You are an intake agent for a data audit workflow. Given an interview artifact, extract metadata.

Return a JSON object via the submit_metadata tool with:
- application_name: the application or system being discussed (best guess from content)
- interview_date: date of the interview if mentioned (YYYY-MM-DD or null)
- interviewees: list of people interviewed (names, titles if available)
- source_type_override: if the content doesn't match the guessed source type, suggest the correct one
  (one of: transcript, interviewer_notes, ba_notes, debrief, client_doc, pre_interview)
- key_topics: list of 3-5 main topics covered"""

METADATA_TOOL = {
    "name": "submit_metadata",
    "description": "Submit extracted metadata for an interview artifact",
    "input_schema": {
        "type": "object",
        "properties": {
            "application_name": {"type": "string"},
            "interview_date": {"type": ["string", "null"]},
            "interviewees": {
                "type": "array",
                "items": {"type": "string"},
            },
            "source_type_override": {"type": ["string", "null"]},
            "key_topics": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["application_name", "interviewees", "key_topics"],
    },
}


def process_interview_inputs(
    file_paths: list[str | Path],
    application_name: str | None = None,
    interview_date: str | None = None,
    interviewees: list[str] | None = None,
) -> tuple[InterviewInputs, AgentTrace]:
    start = time.time()
    client = get_llm_client()
    total_tokens_used = 0
    llm_calls = 0

    documents: list[InputDocument] = []
    detected_app_name = application_name
    detected_date = interview_date
    detected_interviewees = list(interviewees or [])

    for file_path in file_paths:
        path = Path(file_path)
        content = parse_file(path)
        token_count = count_tokens(content)
        guessed_type = guess_source_type(path.name)

        # LLM call for metadata extraction on the first document
        # (or if we don't have application_name yet)
        metadata = {}
        if not detected_app_name:
            preview = content[:3000]
            response = client.complete_with_tools(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"File: {path.name}\n"
                            f"Guessed source type: {guessed_type}\n\n"
                            f"Content preview:\n{preview}"
                        ),
                    }
                ],
                tools=[METADATA_TOOL],
                system=METADATA_SYSTEM_PROMPT,
                max_tokens=1024,
                tool_choice={"type": "tool", "name": "submit_metadata"},
            )

            if response.tool_calls:
                metadata = response.tool_calls[0].arguments

            total_tokens_used += response.usage.input_tokens + response.usage.output_tokens
            llm_calls += 1

            if not detected_app_name:
                detected_app_name = metadata.get("application_name", "Unknown")
            if not detected_date and metadata.get("interview_date"):
                detected_date = metadata["interview_date"]
            if not detected_interviewees and metadata.get("interviewees"):
                detected_interviewees = metadata["interviewees"]

            override = metadata.get("source_type_override")
            if override and override != guessed_type:
                guessed_type = override

        doc = InputDocument(
            filename=path.name,
            source_type=SourceType(guessed_type),
            content=content,
            token_count=token_count,
            metadata=metadata,
        )
        documents.append(doc)

    interview = InterviewInputs(
        application_name=detected_app_name or "Unknown",
        interview_date=detected_date,
        interviewees=detected_interviewees,
        documents=documents,
    )

    duration = time.time() - start
    trace = AgentTrace(
        agent_name="intake",
        phase="C",
        input_summary=f"{len(file_paths)} files for {detected_app_name}",
        output_summary=(
            f"{len(documents)} docs parsed, "
            f"{sum(d.token_count for d in documents)} total tokens"
        ),
        duration_seconds=round(duration, 2),
        llm_calls=llm_calls,
        tokens_used=total_tokens_used,
    )

    return interview, trace


def intake_from_directory(
    directory: str | Path,
    application_name: str | None = None,
) -> tuple[InterviewInputs, AgentTrace]:
    directory = Path(directory)
    supported = {".md", ".txt", ".pdf", ".docx", ".json"}
    file_paths = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in supported
    )

    if not file_paths:
        raise ValueError(f"No supported files found in {directory}")

    return process_interview_inputs(
        file_paths=file_paths,
        application_name=application_name,
    )
