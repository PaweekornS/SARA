# SARA — Product Overview

**SARA (Smart Autonomous Record Agent)** turns a recorded meeting into a written summary and automatically emails follow-up tasks to the people responsible — without a human writing the notes or sending the emails.

## What SARA does today (working end-to-end)

1. **Upload a meeting recording.** A user drags an audio file (or a text/PDF transcript) onto the web app.
2. **Automatic transcription.** The system converts speech to text using a hosted speech-recognition service.
3. **Automatic summarization.** An AI model reads the transcript and produces:
   - An executive summary (bullet points)
   - A list of key decisions
   - A list of action items — each with a task description, an assignee, and a due date
4. **Automatic email dispatch.** SARA sends a formatted HTML email containing the summary and action items to the relevant recipients, with no human review step in between.
5. **Ask follow-up questions.** After a meeting is processed, the user can type questions about it in a chat window (e.g., "What did we decide about the budget?") and get an answer generated from the transcript.
6. **Session history.** Every processed meeting is saved in a sidebar so the user can revisit past meetings, switch between them, or delete them.

This entire flow — upload → transcribe → summarize → email → chat — is implemented and runs today when the system is started via its Docker setup. It is not a mockup or a slide-deck concept.

## What is NOT finished yet (work-in-progress)

- **Who receives the emails is currently hardcoded.** The step that is supposed to look up real meeting participants' email addresses currently returns two fixed test addresses instead of pulling from a real calendar or meeting platform. Real participant emails are meant to come from the AI's reading of the transcript, but nothing yet confirms that this reliably captures every attendee.
- **No login or user accounts.** Anyone with access to the web app can upload meetings and see all sessions; there is no per-user separation of data.
- **No safety net if transcription fails.** If the speech-to-text service errors out, the system currently substitutes a placeholder transcript rather than clearly telling the user the upload failed. This was a deliberate shortcut for demoing the product, not a finished error-handling path.
- **Files are stored temporarily, not permanently.** Uploaded recordings are kept in a temporary folder rather than durable cloud storage, so they are not guaranteed to persist.
- **No automated quality checks.** There is currently no test suite verifying the app keeps working as it changes (see `PROJECT_STATUS.md`).

## Primary use case

**Internal meeting note-taking and task follow-through for teams that don't want to manually write minutes or chase people for action items.** A team records a meeting, uploads it to SARA, and within minutes every assigned person has an email with exactly what they committed to and when it's due — with zero manual writing.

## Who would use this

Any team running recurring meetings (project syncs, client calls, planning sessions) where:
- Action items are discussed verbally but not reliably written down
- Someone currently has to manually write and send a recap email after each meeting
- Team members ask "what did we agree on again?" days later

## Notable current constraint

The transcription and summarization AI is a Thai-language-oriented provider (see `ARCHITECTURE.md`), which suggests the product's initial focus is Thai-language meetings, though no formal accuracy comparison against other languages exists in the codebase — ไม่มีข้อมูลเพียงพอ (not enough information) to state how it performs on English or mixed-language meetings.
