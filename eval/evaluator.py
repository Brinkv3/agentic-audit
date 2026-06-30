from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.models import AnsweredQuestion, AppResult


@dataclass
class QuestionScore:
    question_id: str
    extraction_score: float
    classification_correct: bool
    completeness_correct: bool
    key_facts_found: list[str] = field(default_factory=list)
    key_facts_missed: list[str] = field(default_factory=list)


@dataclass
class AppScore:
    application_name: str
    question_scores: list[QuestionScore] = field(default_factory=list)

    @property
    def avg_extraction(self) -> float:
        scores = [q.extraction_score for q in self.question_scores]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def classification_accuracy(self) -> float:
        total = len(self.question_scores)
        correct = sum(1 for q in self.question_scores if q.classification_correct)
        return correct / total if total else 0.0

    @property
    def completeness_accuracy(self) -> float:
        total = len(self.question_scores)
        correct = sum(1 for q in self.question_scores if q.completeness_correct)
        return correct / total if total else 0.0


@dataclass
class EvalResult:
    app_scores: list[AppScore] = field(default_factory=list)

    @property
    def overall_extraction(self) -> float:
        all_scores = [q.extraction_score for a in self.app_scores for q in a.question_scores]
        return sum(all_scores) / len(all_scores) if all_scores else 0.0

    @property
    def overall_classification(self) -> float:
        total = sum(len(a.question_scores) for a in self.app_scores)
        correct = sum(
            sum(1 for q in a.question_scores if q.classification_correct)
            for a in self.app_scores
        )
        return correct / total if total else 0.0

    @property
    def overall_completeness(self) -> float:
        total = sum(len(a.question_scores) for a in self.app_scores)
        correct = sum(
            sum(1 for q in a.question_scores if q.completeness_correct)
            for a in self.app_scores
        )
        return correct / total if total else 0.0


def _fact_in_answer(fact: str, answer_text: str) -> bool:
    answer_lower = answer_text.lower()
    keywords = [w.strip().lower() for w in fact.split(",")[0].split("(")[0].split() if len(w) > 2]
    if not keywords:
        return False
    matches = sum(1 for kw in keywords if kw in answer_lower)
    return matches / len(keywords) >= 0.5


def evaluate_app_result(
    app_result: AppResult,
    ground_truth: dict,
) -> AppScore:
    expected = ground_truth.get("expected_answers", {})
    answer_map = {a.question_id: a for a in app_result.answered_questions}

    question_scores = []
    for qid, truth in expected.items():
        answer = answer_map.get(qid)
        if not answer:
            question_scores.append(
                QuestionScore(
                    question_id=qid,
                    extraction_score=0.0,
                    classification_correct=False,
                    completeness_correct=False,
                    key_facts_missed=truth["key_facts"],
                )
            )
            continue

        found = []
        missed = []
        for fact in truth["key_facts"]:
            if _fact_in_answer(fact, answer.synthesized_answer):
                found.append(fact)
            else:
                missed.append(fact)

        extraction_score = len(found) / len(truth["key_facts"]) if truth["key_facts"] else 1.0
        classification_correct = answer.answer_type.value == truth["expected_type"]
        completeness_correct = answer.completeness.value == truth["expected_completeness"]

        question_scores.append(
            QuestionScore(
                question_id=qid,
                extraction_score=round(extraction_score, 3),
                classification_correct=classification_correct,
                completeness_correct=completeness_correct,
                key_facts_found=found,
                key_facts_missed=missed,
            )
        )

    return AppScore(
        application_name=app_result.application_name,
        question_scores=question_scores,
    )


def evaluate_engagement(
    app_results: list[AppResult],
    ground_truth_path: str | Path,
) -> EvalResult:
    with open(ground_truth_path) as f:
        ground_truth = json.load(f)

    app_scores = []
    for app_result in app_results:
        app_truth = ground_truth.get("applications", {}).get(app_result.application_name)
        if app_truth:
            app_scores.append(evaluate_app_result(app_result, app_truth))

    return EvalResult(app_scores=app_scores)


def print_eval_report(result: EvalResult):
    print("=" * 60)
    print("EVALUATION REPORT")
    print("=" * 60)
    print(f"Overall Extraction Accuracy:    {result.overall_extraction:.1%}")
    print(f"Overall Classification Accuracy: {result.overall_classification:.1%}")
    print(f"Overall Completeness Accuracy:   {result.overall_completeness:.1%}")
    print()

    for app in result.app_scores:
        print(f"--- {app.application_name} ---")
        print(f"  Extraction:      {app.avg_extraction:.1%}")
        print(f"  Classification:  {app.classification_accuracy:.1%}")
        print(f"  Completeness:    {app.completeness_accuracy:.1%}")

        for q in app.question_scores:
            status = "PASS" if q.extraction_score >= 0.8 else "PARTIAL" if q.extraction_score >= 0.5 else "FAIL"
            class_mark = "Y" if q.classification_correct else "N"
            comp_mark = "Y" if q.completeness_correct else "N"
            print(
                f"  {q.question_id}: extraction={q.extraction_score:.0%} "
                f"class={class_mark} comp={comp_mark} [{status}]"
            )
            if q.key_facts_missed:
                for fact in q.key_facts_missed:
                    print(f"    MISSED: {fact}")
        print()
