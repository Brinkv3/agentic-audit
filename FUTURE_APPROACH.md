# Future Approach — Agentic Audit

Where this project should go when it's time to invest in it again.

---

## Current State (June 2026)

The pipeline works end-to-end: question framework loading (JSON/Excel), intake, answer synthesis with factual/anecdotal classification, principle-based analysis, validation, synthesis with AI observations, and Excel deliverable generation. Eval harness validates extraction accuracy (96.7%), completeness (100%), and classification (70%).

**Practical gap:** ~200K tokens per run with a 40-question framework across 2 applications. For day-to-day use on live engagements, the prompt-based approach via Claude Code (see `PROMPT_GUIDE.md`) is more practical — same model quality, uses the existing subscription, and keeps the human in the loop.

**Provider flexibility:** The pipeline now uses [llm-adapter](https://github.com/Brinkv3/llm-adapter) — swap to Bedrock, Azure OpenAI, or a local model via `.env` with zero code changes. A client with an enterprise Bedrock agreement can drop in their credentials and run the full pipeline within their own AWS boundary.

---

## What to Build Next (Priority Order)

### 1. Local/Private Model Backend

**Problem:** Client data transits the LLM provider's infrastructure.

**Options (ranked by quality vs. privacy trade-off):**

| Option | Quality | Privacy | Cost |
|--------|---------|---------|------|
| Amazon Bedrock (Claude) | Same as API | AWS boundary, your account | Pay-per-token, enterprise agreement |
| Azure OpenAI (GPT-4o) | Comparable | Azure boundary, your account | Pay-per-token |
| Ollama + Llama 3.3 70B | Lower for classification | Fully local | Hardware only |
| Ollama + Qwen 2.5 72B | Competitive for extraction | Fully local | Hardware only |

**Recommendation:** Bedrock is the right move for real consulting use. With `llm-adapter`, this is now a `.env` change — set `LLM_PROVIDER=bedrock` and configure `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`. Same prompts, same tool definitions, same output quality. Data stays in your AWS. No code changes required.

### 2. Classification Calibration

**Problem:** 70% classification accuracy — the model over-classifies as "mixed" when ground truth expects "factual."

**Fix approach:**
- Add classification examples to the Answer Agent system prompt (few-shot)
- Tighten the definition: if the factual core of the answer is verifiable and the anecdotal part is just conversational framing ("I know it's not ideal"), classify as factual with a note
- Add a dedicated classification pass — let the Answer Agent focus on synthesis, then run a separate lightweight call to classify each answer. Separating the tasks may improve both.

### 3. Streaming / Progress UX

**Problem:** 40-question runs take 7-10 minutes with no visibility until completion.

**Fix:** Add streaming output to each agent call. The orchestrator already prints phase markers — extend this to stream partial answers as they're synthesized. For the Excel output, generate a preliminary version after each application completes (not just at the end).

### 4. Incremental Processing

**Problem:** You can't add a new interview without re-running everything.

**Fix:** Persist `AppResult` objects as JSON after each interview. The orchestrator loads prior results and only processes new interviews. The synthesis/deliverable phase always runs fresh (it's fast and needs all data). This also enables the workflow: interview Monday → process Monday night → interview Tuesday → process, accumulating results.

### 5. MCP Server Exposure

Per the original design doc — expose through the consulting MCP server:
- `audit_generate_questions`: engagement docs → suggested questions
- `audit_process_interview`: interview artifacts → answered questions for one app
- `audit_synthesize`: all results → deliverable

This connects the pipeline to the existing MCP infrastructure and lets it be invoked from any MCP-compatible client.

### 6. Notion Integration

**Problem:** Shawn's BA takes notes in Notion during interviews, debriefs happen in Notion.

**Fix:** Add a Notion intake path — pull pages by URL or database query, convert to markdown, feed into the pipeline. The Notion MCP tools are already available in the environment. This eliminates the manual "export from Notion → save as markdown → point pipeline at folder" step.

---

## Architecture Evolution

The current design is sequential: intake → answer → analyze → validate → synthesize. Each agent runs once per application.

**Where parallelism helps:**
- Answer synthesis by category (already chunked, but sequential). These chunks are independent — run them concurrently.
- Multiple applications processed simultaneously (independent until synthesis).
- Analysis and validation could run concurrently (they read the same answers but don't depend on each other).

**Where it doesn't:**
- Validation must come after answers (it reviews them).
- Synthesis must come after all applications are processed (it needs the full picture).

A natural refactor: use `asyncio` for concurrent LLM calls within each phase. The orchestrator becomes an async coordinator. This cuts wall-clock time roughly in half for multi-application runs.

---

## What NOT to Build

- **A UI.** The pipeline is a CLI/library tool. The "UI" is Claude Code or a Jupyter notebook. Building a web frontend adds complexity without adding value for a tool with one user.
- **A database.** JSON files and Excel workbooks are the right persistence layer for this scale. Adding Postgres or SQLite creates operational overhead that doesn't pay off until you're processing 50+ engagements.
- **A generic workflow engine.** This automates one specific consulting workflow. Keep it specific. If you need a different workflow, build a different tool.
