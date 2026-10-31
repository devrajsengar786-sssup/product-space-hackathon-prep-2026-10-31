# DecisionDesk — competition and contribution notes

## Preparation disclosure

Before kickoff, Codex helped inspect/install development tools and prepare a generic Streamlit environment check, launcher, local repository, and dependency snapshot. That preparation did not implement a competition problem. The generic starter was backed up in a private repository using the user's existing GitHub sign-in.

During the hackathon, the user selected Problem 3 and explicitly asked Codex to start building DecisionDesk. Codex generated implementation code, fictional sample meetings, and documentation. The user requested localhost-only operation; no hosted deployment was made. The implementation and fixtures are AI-assisted work, not solely human-written work.

## Problem and intended user

Problem 3 concerns meeting decisions, action items, follow-up, and memory across meetings. DecisionDesk is intended for a small product team that needs to see what was agreed, who owns the next action, when it is due, and whether a later meeting changes an earlier decision.

Official brief: https://theproductspace.in/ai-hackathon-details/problem-statement

Event details: https://theproductspace.in/ai-hackathon-details

Before submission, the user should copy or summarize the exact selected brief and record any kickoff clarifications here. This document does not assert that all requirements have passed judging or been verified with real users.

## Implemented approach

The Streamlit interface accepts typed/pasted meeting text or UTF-8 `.txt` uploads of up to 30,000 characters, previews extraction, highlights incomplete follow-ups and conflicts, and asks for review/approval before updating accepted memory. SQLite stores local meeting records, accepted decisions, and action items at `data/decisiondesk.sqlite3`; this directory is ignored by Git. A navy/teal workspace visual restyle is presentation work and does not change the functional claims below.

The default extraction path is deterministic and rule-based, not live AI. It targets explicit speaker labels, decisions, owners, and dates. An optional local Ollama `/api/chat` path is available for a user-installed model; Ollama 0.40.13 and Qwen3 1.7B are now installed and selected locally. A live fictional two-line smoke check passed in 12.8 seconds. This is not a measurement of real-meeting accuracy.

Saving a meeting and approving its extracted memory are separate steps. When a new decision conflicts with accepted memory, the reviewer can keep the previous decision or replace it. Due-soon reminders are calculated for open approved/published actions with valid due dates and shown inside the app while it is open. Drafts do not create reminders; missing dates must be reviewed. Weekly digest and owner exports are Markdown artifacts. No unattended emails, calendar alarms, or background reminder delivery are implemented.

External GitHub Issues use the existing `gh` sign-in and require a preview, review of the target repository, and explicit confirmation. The initial target is the private preparation repository at https://github.com/devrajsengar786-sssup/product-space-hackathon-prep-2026-10-31 . No issues or social posts should be created merely by importing samples, extracting, or approving local meeting memory.

## Voice and accessibility disclosure

The official brief requires Wispr Flow during building and natural speech captured through Wispr Flow as the product's main input. DecisionDesk accepts text inserted by the installed Wispr app into a focused transcript field. It contains no built-in Wispr API or audio recorder.

The user currently can only type. Typed/pasted transcripts and supported `.txt` uploads are a testing and accessibility fallback; they do not establish compliance with the spoken-input requirement. Actual Wispr use and evidence, an allowed teammate demonstration, or an explicit organizer accessibility exception still need to be recorded. The fictional fixtures and typed input are not recorded speech.

Organizer clarification or accommodation: **not yet recorded**.

Actual Wispr demonstration and evidence: **not yet recorded**.

## Contributions — keep this record current

| Contributor | Contribution | Evidence or details to add before submission |
| --- | --- | --- |
| User/team | Selected Problem 3 and requested DecisionDesk implementation; supplied event context and constraints, including free-only use and typing-only access | Add the team's actual design decisions, testing, edits, and demo preparation |
| Codex | Generated prototype implementation, fictional sample data, documentation, and implementation checks during the hackathon | Record final reviewed files, test results, and any fixes accepted by the user |
| Third-party tools | Python, Streamlit, SQLite, Git/GitHub CLI, and optional local Ollama | Record any additional models, libraries, borrowed code, licenses, or credits actually used |

Do not claim a provider/model was used merely because an SDK is installed. No paid API requests or newly registered accounts are part of this implementation.

## Validation record

Run from the project folder:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

**31 October 2026: the complete automated suite passed — 53 tests.** The breakdown is 15 extraction/local-provider-boundary tests, 22 SQLite/store and mocked tracker-adapter tests, 12 workspace-feature tests, and 4 Streamlit UI workflow tests. Tests use fictional inputs and temporary databases.

Covered and passing:

- Offline extraction of explicit speakers, decisions, owners, ISO/relative dates, and spoken corrections; missing owner/date warnings; invalid/oversized input and prompt-control filtering.
- Local-model request/schema/evidence validation, remote-endpoint rejection, unsupported-owner/date removal, and provider failure without silent offline fallback. Ollama responses were mocked; no real AI call was made.
- Draft isolation from accepted memory and reminders; explicit conflict resolution; keep-previous and replacement paths; stale-review protection; idempotent reapproval; valid action status changes; due-date and weekly-digest calculations.
- SQLite-backed state across store connections and Streamlit reruns. A full computer restart was not part of this verification.
- UI capture → extraction → review → approval and second-meeting conflict handling, plus action status changes and the decision-memory/digest/connections/overview screens.
- GitHub publishing confirmation gates, draft refusal, duplicate prevention, timeout handling without automatic retries, and reset of app consent when the repository or chosen tasks change. All issue-creation calls in tests were mocked.

**Local browser check:** loaded the fictional planning meeting, extracted it, and opened the review screen showing source evidence plus incomplete owner/date warnings. No approval was clicked in this browser check. The automated UI tests separately exercised approval using temporary test data.

Remaining real-world checks and deliverables:

- Actual GitHub issue creation: **not demonstrated; no issue was posted; requires explicit app confirmation**.
- Local Ollama model and real AI extraction: **basic live fictional smoke check passed**; broader meeting quality remains unmeasured.
- Wispr dictation and evidence/accessibility approval: **not demonstrated for this product; accommodation still pending**.
- Full computer-restart/relaunch check, actual export-file playback/opening, and final visual QA after styling: **not recorded here**.
- Three-minute demo video and judge access to the video/code: **not prepared or verified**.

No GitHub Issues, Wispr recordings, social posts, or hosted deployments were made. Automated provider tests use mocks; the later live local-model check used fictional meeting text.

The Atlas transcripts are fictional and generated for this demo. No real-user accuracy, time saved, adoption, or performance metrics have been measured. The rule-based path may miss complex language and must be reviewed before acceptance or external action.

## Submission checklist and links

- Repository: https://github.com/devrajsengar786-sssup/product-space-hackathon-prep-2026-10-31 — currently private; confirm judging access before submission.
- Three-minute demo video: **to be recorded and checked**.
- Demo deployment: **localhost-only, as requested by the user**. No hosted demo is being published; a localhost URL is accessible only on this computer.
- Wispr evidence or written accessibility accommodation: **to be supplied**.
- Brief problem, architecture, and contribution explanation: **review and complete this document**.
- Project deadline: **31 October 2026, 11:59 PM IST**.
- LinkedIn links and engagement screenshots, if submitted: **to be prepared by the user**; deadline **1 November 2026, 11:59 PM IST**.

Check that demo/video/code links work with the access the judges will have. Do not publish credentials, local database files, confidential meeting transcripts, or fabricated voice evidence.


Professional features added 31 October: isolated project workspaces; local backup/validated atomic restore into an empty workspace; search with source links; accepted decision timeline; latest-meeting changes; priorities, dependency cycle checks and completion blocking; all-day calendar export; measured team workload and completion. New tests cover these behaviors, workspace switching and consent isolation. Browser verification confirmed the updated navy/teal dashboard serving on localhost.


Local AI setup completed: official installer signature verified as Ollama Inc.; model files obtained from the official Ollama registry and SHA-256 checked before installation. Installed Qwen3 0.6B and 1.7B; selected 1.7B after the smaller model overclassified dated commitments. Improved source validation filters clear task promises out of decision memory and explains omissions. Live verification checked one decision, one action, its named owner/deadline, and source evidence. Timing is one machine/sample observation only. Local inference is free of paid API calls; downloading the app/model required network access. No claims of production readiness or real meeting accuracy are made.
