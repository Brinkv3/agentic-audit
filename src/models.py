from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AnswerType(str, Enum):
    FACTUAL = "factual"
    ANECDOTAL = "anecdotal"
    MIXED = "mixed"


class Completeness(str, Enum):
    FULL = "fully_answered"
    PARTIAL = "partially_answered"
    NOT_ADDRESSED = "not_addressed"


class SourceType(str, Enum):
    TRANSCRIPT = "transcript"
    INTERVIEWER_NOTES = "interviewer_notes"
    BA_NOTES = "ba_notes"
    DEBRIEF = "debrief"
    CLIENT_DOC = "client_doc"
    PRE_INTERVIEW = "pre_interview"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ---------------------------------------------------------------------------
# Phase A — Question Framework
# ---------------------------------------------------------------------------

class Question(BaseModel):
    id: str
    category: str
    text: str
    context: Optional[str] = None


class QuestionFramework(BaseModel):
    engagement_name: str
    questions: list[Question]
    locked: bool = False
    source: str = "ai_generated"


# ---------------------------------------------------------------------------
# Phase B/C — Interview Inputs
# ---------------------------------------------------------------------------

class InputDocument(BaseModel):
    filename: str
    source_type: SourceType
    content: str
    token_count: int = 0
    metadata: dict = Field(default_factory=dict)


class InterviewInputs(BaseModel):
    application_name: str
    interview_date: Optional[str] = None
    interviewees: list[str] = Field(default_factory=list)
    documents: list[InputDocument] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase C — Answered Questions
# ---------------------------------------------------------------------------

class SourceCitation(BaseModel):
    source_type: SourceType
    filename: str
    excerpt: str


class AnsweredQuestion(BaseModel):
    question_id: str
    question_text: str
    synthesized_answer: str
    answer_type: AnswerType
    confidence: int = Field(ge=0, le=100)
    completeness: Completeness
    sources: list[SourceCitation] = Field(default_factory=list)
    conflicts: Optional[str] = None


class Finding(BaseModel):
    principle_id: str
    principle_name: str
    severity: Severity
    observation: str
    evidence: str
    recommendation: str
    is_positive: bool = False


class AIObservation(BaseModel):
    observation: str
    evidence: str
    source_interviews: list[str] = Field(default_factory=list)
    suggested_followup: Optional[str] = None


# ---------------------------------------------------------------------------
# Per-Application Result (output of Phase C for one interview)
# ---------------------------------------------------------------------------

class AppResult(BaseModel):
    application_name: str
    interview_date: Optional[str] = None
    interviewees: list[str] = Field(default_factory=list)
    answered_questions: list[AnsweredQuestion] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    input_summary: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase D — Deliverable
# ---------------------------------------------------------------------------

class CoverageCell(BaseModel):
    question_id: str
    application_name: str
    completeness: Completeness


class EngagementResult(BaseModel):
    engagement_name: str
    question_framework: QuestionFramework
    app_results: list[AppResult] = Field(default_factory=list)
    coverage_matrix: list[CoverageCell] = Field(default_factory=list)
    ai_observations: list[AIObservation] = Field(default_factory=list)
    summary: Optional[str] = None


# ---------------------------------------------------------------------------
# Workflow Trace
# ---------------------------------------------------------------------------

class AgentTrace(BaseModel):
    agent_name: str
    phase: str
    input_summary: str
    output_summary: str
    duration_seconds: float = 0.0
    llm_calls: int = 0
    tokens_used: int = 0


class WorkflowTrace(BaseModel):
    engagement_name: str
    agents: list[AgentTrace] = Field(default_factory=list)
    total_duration_seconds: float = 0.0
    total_tokens: int = 0
