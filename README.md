# Agentic Audit — Data Audit Discovery Automation

A multi-agent workflow system that automates the consulting data audit discovery process: generate interview questions from engagement documents, process interview artifacts, synthesize answers with factual/anecdotal classification, evaluate against architectural principles, and produce a client-ready Excel deliverable.

## What It Does

```
Engagement documents + Interview artifacts
        ↓
  Question Generation Agent → locked question framework
        ↓
  Intake Agent → parsed, tagged interview inputs
        ↓
  Answer Agent → per-question synthesis across all sources
        ↓
  Analysis Agent → findings against architectural principles
        ↓
  Validation Agent → cross-checked, confidence-scored answers
        ↓
  Synthesis Agent → executive summary + AI observations
        ↓
  Excel workbook (per-app tabs, coverage matrix, gaps, observations)
```

Every answer is classified as **factual** (grounded in process, rule, or system documentation) or **anecdotal** (opinion, interpretation, unverified claim). A client acting on anecdotal data needs to know it's anecdotal.

## Key Design Decisions

- **Questions are the organizing frame.** Everything maps back to the interview questions. The system answers each question as completely as possible — not free extraction.
- **Claude native tool calling.** No framework dependency. Each agent uses structured tool definitions for typed output.
- **Pydantic models for inter-agent state.** Typed, validated, serializable contracts between agents.
- **Configurable architectural principles.** Pattern evaluation loaded from JSON config — same schema-driven approach for any engagement.
- **Evaluation from Day 1.** Extraction accuracy, classification accuracy, and completeness accuracy measured against ground truth.

## Quick Start

```bash
git clone https://github.com/Brinkv3/agentic-audit.git
cd agentic-audit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Anthropic API key
```

### Run the evaluation pipeline

```bash
python -m eval.run_eval
```

Processes two sample applications (Payroll System, CRM Platform) against a 10-question framework with ground truth, reports extraction/classification/completeness accuracy.

### Run against your own data

```python
from src.orchestrator import AuditOrchestrator

orchestrator = AuditOrchestrator("My Engagement")

# Load questions from Excel or JSON
orchestrator.load_questions("path/to/questions.xlsx")
orchestrator.lock_questions()

# Process each interview (point at a folder of artifacts)
orchestrator.process_interview(directory="path/to/app_artifacts/")

# Generate the deliverable
orchestrator.generate_deliverable("output/my_audit.xlsx")
```

## Project Structure

```
agentic-audit/
├── PROMPT_GUIDE.md         ← Practitioner's guide for prompt-based workflow
├── config/
│   └── principles.json     ← Architectural principles for pattern evaluation
├── src/
│   ├── models.py           ← Pydantic models (14 types, full agent contract layer)
│   ├── question_gen.py     ← Question Generation Agent (Phase A)
│   ├── intake.py           ← Intake Agent: parse and tag interview inputs
│   ├── answer.py           ← Answer Agent: per-question synthesis across sources
│   ├── analysis.py         ← Analysis Agent: evaluate against principles
│   ├── validation.py       ← Validation Agent: cross-check, conflicts, confidence
│   ├── synthesis.py        ← Synthesis Agent: summary + AI observations
│   ├── orchestrator.py     ← Workflow orchestration and state management
│   ├── excel_output.py     ← Excel workbook generation (openpyxl)
│   └── utils.py            ← File parsing, config loading, shared utilities
├── eval/
│   ├── test_interviews/    ← Sample interview artifacts (realistic, anonymized)
│   ├── test_questions.json ← Sample question framework
│   ├── ground_truth.json   ← Expected answers and classifications
│   ├── evaluator.py        ← Extraction + classification + completeness scoring
│   └── run_eval.py         ← End-to-end evaluation runner
└── output/                 ← Generated Excel deliverables
```

## Evaluation Results

Against the test corpus (2 applications, 10 questions each):

| Metric | Score |
|--------|-------|
| Extraction Accuracy | 96.7% |
| Completeness Accuracy | 100% |
| Classification Accuracy | 70% |

Classification accuracy reflects calibration differences in factual vs. mixed categorization — the model sometimes classifies answers as "mixed" when the ground truth expects "factual" because the answer includes both documented facts and editorial commentary from the interviewee.

## Architecture Principles (Configurable)

Default principles loaded from `config/principles.json`:

- **Lakehouse as source of truth** — all apps store/retrieve from the central data layer
- **No application-to-application dependencies** — data flows through integration layers, not point-to-point
- **Enterprise SaaS via direct API** — Workday, Salesforce, etc. accessed through native APIs

Add engagement-specific principles by editing the config file.

## Dependencies

```
anthropic       # Claude API
pydantic        # Typed inter-agent state models
openpyxl        # Excel workbook generation
PyMuPDF         # PDF parsing
python-docx     # DOCX parsing
pandas          # Structured data handling
tiktoken        # Token counting
python-dotenv   # Environment config
pytest          # Test harness
```

## Portfolio Context

| Repo | Demonstrates |
|------|-------------|
| [`rag-pipeline`](https://github.com/Brinkv3/rag-pipeline) | Retrieval, grounding, evaluation, governance, multi-agent orchestration |
| [`doc-intelligence`](https://github.com/Brinkv3/doc-intelligence) | Classification, structured extraction, cross-document reasoning |
| [`consulting-mcp-server`](https://github.com/Brinkv3/consulting-mcp-server) | Protocol interoperability — unified tool surface over MCP |
| **`agentic-audit`** (this) | End-to-end agentic workflow automation for a real consulting process |

## License

MIT — Carter Brinkley Consulting LLC
