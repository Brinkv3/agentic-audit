from __future__ import annotations

import json
import time
from pathlib import Path

from src.analysis import analyze_against_principles
from src.answer import synthesize_answers
from src.excel_output import generate_workbook
from src.intake import intake_from_directory, process_interview_inputs
from src.models import (
    AppResult,
    EngagementResult,
    QuestionFramework,
    WorkflowTrace,
)
from src.question_gen import (
    export_framework_json,
    generate_questions,
    load_questions_from_excel,
    load_questions_from_json,
    lock_framework,
)
from src.synthesis import synthesize_engagement
from src.utils import OUTPUT_DIR
from src.validation import validate_answers


def _log(msg: str):
    print(msg, flush=True)


class AuditOrchestrator:
    def __init__(self, engagement_name: str):
        self.engagement_name = engagement_name
        self.framework: QuestionFramework | None = None
        self.app_results: list[AppResult] = []
        self.trace = WorkflowTrace(engagement_name=engagement_name)
        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Phase A: Question Framework
    # ------------------------------------------------------------------

    def generate_questions(self, engagement_docs: list[str | Path]) -> QuestionFramework:
        _log(f"[Phase A] Generating questions from {len(engagement_docs)} documents...")
        framework, trace = generate_questions(engagement_docs, self.engagement_name)
        self.framework = framework
        self.trace.agents.append(trace)
        _log(f"[Phase A] Generated {len(framework.questions)} questions")
        return framework

    def load_questions(self, filepath: str | Path) -> QuestionFramework:
        filepath = Path(filepath)
        _log(f"[Phase A] Loading questions from {filepath.name}...")
        if filepath.suffix.lower() in (".xlsx", ".xls"):
            self.framework = load_questions_from_excel(
                filepath, engagement_name=self.engagement_name
            )
        else:
            self.framework = load_questions_from_json(filepath)
            self.framework = self.framework.model_copy(
                update={"engagement_name": self.engagement_name}
            )
        _log(f"[Phase A] Loaded {len(self.framework.questions)} questions")
        return self.framework

    def lock_questions(self) -> QuestionFramework:
        if not self.framework:
            raise ValueError("No question framework to lock")
        self.framework = lock_framework(self.framework)
        _log(f"[Phase A] Framework locked with {len(self.framework.questions)} questions")
        return self.framework

    def export_questions(self, output_path: str | Path | None = None) -> Path:
        if not self.framework:
            raise ValueError("No question framework to export")
        output_path = output_path or OUTPUT_DIR / f"{self.engagement_name}_questions.json"
        return export_framework_json(self.framework, output_path)

    # ------------------------------------------------------------------
    # Phase C: Process one interview
    # ------------------------------------------------------------------

    def process_interview(
        self,
        file_paths: list[str | Path] | None = None,
        directory: str | Path | None = None,
        application_name: str | None = None,
    ) -> AppResult:
        if not self.framework or not self.framework.locked:
            raise ValueError("Question framework must be locked before processing interviews")

        # Intake
        if directory:
            _log(f"[Phase C] Intake: processing directory {directory}...")
            inputs, intake_trace = intake_from_directory(directory, application_name)
        elif file_paths:
            _log(f"[Phase C] Intake: processing {len(file_paths)} files...")
            inputs, intake_trace = process_interview_inputs(file_paths, application_name)
        else:
            raise ValueError("Provide either file_paths or directory")

        self.trace.agents.append(intake_trace)
        _log(f"[Phase C] Intake complete: {inputs.application_name}, {len(inputs.documents)} docs")

        # Answer synthesis
        _log(f"[Phase C] Synthesizing answers for {inputs.application_name}...")
        answered, answer_trace = synthesize_answers(self.framework, inputs)
        self.trace.agents.append(answer_trace)
        _log(f"[Phase C] Synthesized {len(answered)} answers")

        # Analysis against principles
        _log(f"[Phase C] Analyzing against principles...")
        findings, analysis_trace = analyze_against_principles(
            answered, inputs.application_name
        )
        self.trace.agents.append(analysis_trace)
        _log(f"[Phase C] Found {len(findings)} findings")

        # Validation
        _log(f"[Phase C] Validating answers...")
        validated, validation_trace = validate_answers(answered, inputs.application_name)
        self.trace.agents.append(validation_trace)
        _log(f"[Phase C] Validation complete")

        app_result = AppResult(
            application_name=inputs.application_name,
            interview_date=inputs.interview_date,
            interviewees=inputs.interviewees,
            answered_questions=validated,
            findings=findings,
            input_summary={
                "document_count": len(inputs.documents),
                "source_types": [d.source_type.value for d in inputs.documents],
                "total_tokens": sum(d.token_count for d in inputs.documents),
            },
        )

        self.app_results.append(app_result)
        return app_result

    # ------------------------------------------------------------------
    # Phase D: Generate deliverable
    # ------------------------------------------------------------------

    def generate_deliverable(self, output_path: str | Path | None = None) -> Path:
        if not self.framework:
            raise ValueError("No question framework")
        if not self.app_results:
            raise ValueError("No interview results to synthesize")

        _log(f"[Phase D] Synthesizing engagement results...")
        engagement_result, synthesis_trace = synthesize_engagement(
            self.framework, self.app_results
        )
        self.trace.agents.append(synthesis_trace)

        output_path = output_path or OUTPUT_DIR / f"{self.engagement_name}_audit.xlsx"
        _log(f"[Phase D] Generating Excel workbook...")
        workbook_path = generate_workbook(engagement_result, output_path)

        self.trace.total_duration_seconds = round(time.time() - self._start_time, 2)
        self.trace.total_tokens = sum(a.tokens_used for a in self.trace.agents)

        _log(f"[Phase D] Deliverable generated: {workbook_path}")
        _log(f"[Trace] Total duration: {self.trace.total_duration_seconds}s")
        _log(f"[Trace] Total tokens: {self.trace.total_tokens}")
        _log(f"[Trace] Agent calls: {len(self.trace.agents)}")

        return workbook_path

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def run_full_pipeline(
        self,
        engagement_docs: list[str | Path] | None = None,
        questions_path: str | Path | None = None,
        interview_dirs: list[str | Path] | None = None,
        interview_files: dict[str, list[str | Path]] | None = None,
        output_path: str | Path | None = None,
    ) -> Path:
        # Phase A
        if questions_path:
            self.load_questions(questions_path)
        elif engagement_docs:
            self.generate_questions(engagement_docs)
        else:
            raise ValueError("Provide engagement_docs or questions_path")

        self.lock_questions()

        # Phase C
        if interview_dirs:
            for interview_dir in interview_dirs:
                self.process_interview(directory=interview_dir)
        elif interview_files:
            for app_name, files in interview_files.items():
                self.process_interview(file_paths=files, application_name=app_name)
        else:
            raise ValueError("Provide interview_dirs or interview_files")

        # Phase D
        return self.generate_deliverable(output_path)

    def get_trace(self) -> dict:
        return self.trace.model_dump()
