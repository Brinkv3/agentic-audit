# Data Audit Discovery — Prompt Guide

A practitioner's guide for running the data audit discovery workflow using Claude Code (or any Claude interface with file access). This is the "use it now" companion — load your interview artifacts, apply the prompt template, get client-ready output.

---

## Setup

Organize your interview artifacts by application:

```
engagement/
├── questions.xlsx              ← Your locked question framework
├── app_1_name/
│   ├── transcript.md           ← Meeting transcript
│   ├── interviewer_notes.md    ← Your notes during the interview
│   ├── ba_notes.md             ← BA's notes (if applicable)
│   ├── debrief.md              ← Post-interview debrief
│   └── client_docs/            ← Any pre-interview materials
│       └── architecture.pdf
├── app_2_name/
│   ├── transcript.md
│   ├── interviewer_notes.md
│   └── debrief.md
└── engagement_docs/            ← SOW, proposal, contract (for question generation)
    ├── sow.pdf
    └── proposal.docx
```

**File naming matters.** Include the type in the filename: `transcript`, `notes`, `debrief`, `ba_notes`. This helps Claude understand each document's role and weight.

---

## Prompt Templates

### 1. Answer Synthesis (Core Workflow)

Use this after each interview. Point Claude at one application's folder plus your question framework.

```
I need you to synthesize answers for a data audit interview. Here is the context:

**Application:** [App Name]
**Interview Date:** [Date]
**Interviewees:** [Names and titles]

**Question Framework:** @questions.xlsx (use the "App 1" tab)

**Interview Artifacts:**
@app_name/transcript.md
@app_name/interviewer_notes.md
@app_name/debrief.md
[add any additional files]

For EACH question in the framework, search across ALL provided documents and produce:

1. **Synthesized Answer** — the most complete and accurate answer from all sources combined
2. **Answer Type** — classify as:
   - **Factual**: grounded in documented process, rule, or verifiable system behavior
     (e.g., "Our pipeline runs nightly via Airflow")
   - **Anecdotal**: opinion, interpretation, single-person perspective, unverified claim
     (e.g., "I think we pull from the lakehouse")
   - **Mixed**: some parts factual, some anecdotal — note which parts are which
3. **Confidence** (0-100): how well-supported across the inputs
4. **Completeness**: Fully Answered / Partially Answered / Not Addressed
5. **Sources**: which documents contributed, with brief excerpts
6. **Conflicts**: if sources disagree, flag both perspectives

Rules:
- If a question wasn't addressed in ANY source, mark "Not Addressed" with confidence 0
- Never invent information — only synthesize from what's in the documents
- The transcript has raw detail, the debrief has interpretation, notes have observations the recording may have missed — weight accordingly
- "The person said X" is anecdotal. "The documentation shows X" is factual.

Output as a structured table I can paste into the question framework Excel, with columns:
Question | Synthesized Answer | Type (F/A/M) | Confidence | Completeness | Sources | Conflicts
```

### 2. Question Generation (Phase A)

Use this when starting a new engagement to generate interview questions from scope documents.

```
I'm starting a data audit engagement. Generate interview questions based on these engagement documents:

@engagement_docs/sow.pdf
@engagement_docs/proposal.docx
[add any additional scope documents]

Extract the scope, systems in play, deliverables, and constraints. Then generate targeted interview questions organized by these categories:

1. Application Identity & Ownership
2. Data Landscape (sources, flows, system of record, PII)
3. Integration Mechanics (technologies, middleware, credentials, error handling)
4. Governance & Change Management (process, review, communication)
5. Pain Points & Known Issues
6. Future State & Aspirations

For each question:
- Make it specific to the systems and scope mentioned in the documents
- Target data usage patterns, integration patterns, dependencies, and pain points
- Frame questions to reveal architecture — not just "what" but "how" and "why"

Generate 30-45 questions. I'll review, edit, and merge with my standard question set.
```

### 3. Cross-Application Analysis (After Multiple Interviews)

Use this after processing 2+ applications to find cross-cutting patterns.

```
I've completed data audit interviews for the following applications:

@app_1/[all artifacts]
@app_2/[all artifacts]
@app_3/[all artifacts]

Analyze across ALL applications and surface:

1. **Cross-Application Data Dependencies** — which apps depend on each other for data? Map the flows.

2. **Architecture Pattern Assessment** — evaluate against these principles:
   - Lakehouse/data warehouse should be the central data hub
   - No direct application-to-application data dependencies
   - Enterprise SaaS (Workday, Salesforce, etc.) accessed via native APIs
   Flag violations and affirm good patterns.

3. **Common Pain Points** — themes that appeared across multiple interviews

4. **Governance Gaps** — ownership ambiguity, undocumented integrations, shadow IT patterns

5. **AI Observations** — patterns, risks, or insights that no question explicitly asked about but that a good consultant would flag. Include suggested follow-up questions.

6. **Coverage Gaps** — questions that were poorly answered or not addressed across applications. These are candidates for follow-up interviews.

For each finding, cite the specific application(s) and source documents.
```

### 4. Excel Deliverable Generation

After synthesis, use this to get formatted output.

```
Based on the synthesized answers for [App Name], generate an Excel-ready output with these tabs:

**Per-Application Tab:**
Columns: Question ID | Category | Question | Synthesized Answer | Type (Factual/Anecdotal/Mixed) | Confidence | Completeness | Sources | Conflicts/Notes

**Format the data as a markdown table I can copy into Excel, or generate the .xlsx directly using the /xlsx skill.**
```

---

## Tips for Best Results

**Weighting sources:** Tell Claude how to weight conflicting information:
- Transcripts have the raw words but may include hedging or social dynamics
- Debrief notes reflect the consultant's interpreted takeaway
- Interviewer notes capture real-time observations the recording missed
- Client-provided documentation is the strongest factual source

**Iterative refinement:** Run the synthesis, review the output, then ask follow-up:
```
For Q-DL-003, the answer seems incomplete. The transcript at [timestamp/section]
mentions something about a nightly batch — can you re-examine that section and
update the answer?
```

**Partial inputs:** Not every interview produces all artifact types. Tell Claude what's available:
```
Note: For this interview, I only have the transcript and my notes.
There was no BA present and we skipped the debrief. Work with what's available
and flag where additional sources would have helped.
```

**PII handling:** If your transcripts contain real names, systems, or sensitive details, note that Claude API has zero data retention by default. For additional protection, anonymize before processing or route through Amazon Bedrock within your own AWS boundary.

---

## Workflow Summary

```
Per Interview:
  1. Collect artifacts → folder per application
  2. Run Answer Synthesis prompt → get structured answers
  3. Review, refine, paste into question framework Excel
  4. Repeat for each application

After All Interviews:
  5. Run Cross-Application Analysis prompt
  6. Generate deliverable tabs (coverage matrix, gaps, findings)
  7. Compile Excel workbook for client delivery
```
