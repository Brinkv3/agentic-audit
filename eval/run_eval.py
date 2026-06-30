"""
End-to-end evaluation runner.

Usage:
    python -m eval.run_eval
"""
from __future__ import annotations

import sys
from pathlib import Path

from eval.evaluator import evaluate_engagement, print_eval_report
from src.orchestrator import AuditOrchestrator

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

EVAL_DIR = Path(__file__).resolve().parent
TEST_QUESTIONS = EVAL_DIR / "test_questions.json"
GROUND_TRUTH = EVAL_DIR / "ground_truth.json"
INTERVIEW_DIRS = [
    EVAL_DIR / "test_interviews" / "payroll_system",
    EVAL_DIR / "test_interviews" / "crm_platform",
]


def main():
    orchestrator = AuditOrchestrator(engagement_name="Acme Corp Data Audit")

    orchestrator.load_questions(TEST_QUESTIONS)
    orchestrator.lock_questions()

    for interview_dir in INTERVIEW_DIRS:
        print(f"\nProcessing: {interview_dir.name}")
        orchestrator.process_interview(directory=interview_dir)

    output_path = orchestrator.generate_deliverable()
    print(f"\nDeliverable: {output_path}")

    print("\n")
    eval_result = evaluate_engagement(orchestrator.app_results, GROUND_TRUTH)
    print_eval_report(eval_result)

    trace = orchestrator.get_trace()
    print(f"\nWorkflow Trace:")
    print(f"  Total duration: {trace['total_duration_seconds']}s")
    print(f"  Total tokens:   {trace['total_tokens']}")
    print(f"  Agent calls:    {len(trace['agents'])}")
    for agent in trace["agents"]:
        print(f"    {agent['agent_name']} ({agent['phase']}): {agent['output_summary']}")


if __name__ == "__main__":
    main()
