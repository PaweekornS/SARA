# SARA — Glossary

Plain-language explanations of the technical terms used across these documents.

**ASR (Automatic Speech Recognition)**
The technology that converts spoken audio into written text. In SARA, this is the first step: turning an uploaded meeting recording into a text transcript.

**LLM (Large Language Model)**
An AI model trained to understand and generate human language. SARA uses one to read the meeting transcript and produce a summary, a list of decisions, and a list of action items.

**Action item**
A task that came out of the meeting — who needs to do what, by when. SARA tries to detect these automatically from what was said.

**MCP (Model Context Protocol)**
An open standard that lets an AI system trigger real-world actions (like "send this email") through a standardized interface, rather than through custom one-off code. Think of it like a universal plug — instead of the backend having its own private way of sending emails, it "plugs in" to a separate email-sending service using a shared, documented format. This makes it easier to add new automated actions later without rebuilding the whole system.

**Celery**
A background job system. When a meeting is uploaded, transcribing and summarizing it can take a while — Celery lets that work happen in the background instead of making the user wait on a frozen screen.

**Redis**
A fast, temporary data store used here purely as the "to-do list" that tells Celery which background jobs need to run.

**SMTP**
The standard protocol used to send email over the internet (the same technology behind sending email from Gmail or Outlook). SARA uses it to deliver the summary emails.

**API (Application Programming Interface)**
The set of "doors" the frontend (website) uses to talk to the backend (server) — for example, "upload this file" or "check if this meeting is done processing."

**Backend / Frontend**
The **frontend** is what the user sees and clicks in their browser. The **backend** is the server behind the scenes that stores data, talks to AI services, and does the heavy lifting.

**Repository (repo) / Commit**
A repository is the project's complete file history, stored with Git. A commit is one saved snapshot of changes — like a save-point in a document's revision history.

**CI/CD (Continuous Integration / Continuous Deployment)**
Automated systems that test and publish new code changes automatically. SARA does not currently have this — code changes are tested and released manually.

**Docker / Docker Compose**
Docker packages an application (with everything it needs to run) into a standardized, portable unit called a "container." Docker Compose is a tool for running several containers together (e.g., the database, the backend, and the frontend) with one command — used here to run the whole SARA system on one machine.

**Open-source license (MIT, Apache-2.0, BSD, LGPL)**
Legal terms under which a piece of free software can be used. **MIT, Apache-2.0, and BSD** are "permissive" — they place very few restrictions on commercial use. **LGPL** is more restrictive ("copyleft") but generally still allows commercial use as long as certain conditions are met — this is why it's flagged for a legal review rather than treated as a blocker.

**LOC (Lines of Code)**
A rough measure of codebase size — literally, how many lines of source code exist. Useful for gauging project maturity, not code quality.
