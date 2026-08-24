# SARA — Technical Differentiation

This document is written for honesty rather than sales polish: it states plainly what is and isn't a defensible technical advantage based on what actually exists in the code today.

## What is genuinely distinctive about the current build

**End-to-end autonomous dispatch, with no human approval step.**
Most meeting-summary tools (Otter.ai, Fireflies, Fathom, etc.) generate a summary and stop — a human still has to read it, decide who needs which task, and send follow-ups. SARA's pipeline goes one step further: the LLM is asked to extract *who is responsible* and *their email address* directly from natural, unstructured meeting speech (e.g., "Jane will write the docs, send it to jane@example.com"), and the system emails that person automatically, with no review step in between. This "extract contacts + tasks from speech, then act on them automatically" behavior is the one part of the pipeline that goes beyond standard transcription/summarization tooling.

**Built on the Model Context Protocol (MCP) for the action step.**
The email-dispatch step isn't a hardcoded function call inside the backend — it's implemented as a standalone MCP server exposing a `send_meeting_summary_email` tool, which the backend calls as an MCP client over SSE. MCP is an emerging, cross-vendor standard (backed by Anthropic and increasingly adopted industry-wide) for connecting AI systems to external actions/tools. Architecting the "do something in the real world" step this way — rather than as backend-specific glue code — means this action layer could, in principle, be reused or plugged into other MCP-compatible AI agents/orchestrators without rewriting it, and new "actions" (e.g., a Slack-notify tool, a calendar-update tool) could be added as additional MCP tools rather than new bespoke integrations.

## What is NOT a differentiator (and should not be pitched as one)

Being direct about this protects credibility with technical due diligence:

- **The email-sending logic itself is boilerplate.** The `send_meeting_summary_email` tool is a Jinja2 HTML template rendered and sent via standard SMTP in a loop — no custom algorithm, retry logic, or delivery optimization.
- **No custom ML model or training pipeline exists.** Transcription and summarization both call a third-party hosted AI API (AI4Thai/Pathumma); SARA does not train, fine-tune, or host its own model.
- **No proprietary dataset.** The system does not build, store, or learn from a dataset of its own — each meeting is processed independently.
- **No benchmark results exist in this codebase.** There is no test, script, or report in this repo comparing SARA's transcription accuracy, summarization quality, or speed against any competing product. ไม่มีข้อมูลเพียงพอ — any competitive-accuracy claim would need to be produced separately (e.g., a manual evaluation study) before it could be included here.

## Possible market angle worth validating (not yet proven)

The underlying AI provider (AI4Thai/Pathumma) is oriented toward the Thai language. This suggests the product may currently perform better on Thai-language meetings than English-language meeting tools built primarily around English-first models — but this is an inference from the vendor configuration, not a validated result. No accuracy comparison, user study, or benchmark exists to confirm this. If Thai-language accuracy is genuinely a differentiator, it would need to be demonstrated with real evaluation data before being used in an investor pitch.

## Barrier to replication, realistically

For a competent engineering team, replicating the current feature set (upload → transcribe → summarize → auto-email → chat Q&A) using off-the-shelf APIs is not a large technical moat — the pipeline is a sequence of well-known building blocks (FastAPI, Celery, a hosted ASR/LLM API, SMTP). What would take a competitor more time to replicate is not the code, but two non-technical assets: (1) any accumulated tuning of prompts/heuristics for reliably extracting names, emails, and due dates from real unstructured meeting speech in production use, and (2) any real-world validation data showing the extraction is accurate enough to trust without human review — both of which require production usage to build, not just engineering time. Neither of these currently exists as a documented artifact in the repository.
