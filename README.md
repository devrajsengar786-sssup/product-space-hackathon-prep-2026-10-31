# DecisionDesk

DecisionDesk is a hackathon prototype for Problem 3: turn meeting notes into reviewable decisions and action items, keep accepted memory across meetings, and flag changes before updating that memory. The included Atlas meetings are fictional.

## Public demo status — 31 October 2026

The user authorized a separate, free public demo after initially requesting localhost-only operation. [Open the temporary live demo](https://edited-greatest-combinations-council.trycloudflare.com). The host computer must stay awake and online, with the app, tunnel and Ollama running; this is **not always-on cloud hosting**. Use the recorded submission video if the live link is unavailable.

The demo isolates visitor workspaces, uses clearly labelled fictional fixtures and disables GitHub credential checks/publishing at the integration boundary. AI inference still runs on the host computer with Ollama/Qwen3 1.7B. Do not submit private meeting content. See [public demo operation and limits](docs/Public-demo.md). The ordinary localhost app remains available separately. All 84 automated checks passed after these changes, including public-mode isolation and publishing guards.

## Run locally

Double-click **Start app.cmd**. The launcher starts Streamlit and opens http://127.0.0.1:8501. It reuses a server already running at that address. Keep the launcher window open when it starts the server; use Ctrl+C to stop it. Run the launcher again after a computer restart.

Alternatively, open a terminal in this folder:

```powershell
.\.venv\Scripts\python.exe launch.py
```

The existing project environment reuses this computer's installed Python packages through `system-site-packages`; new project packages live in `.venv`. A fresh, isolated environment can be created with:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

`requirements-lock.txt` is a snapshot of versions used locally. A fresh installation on another computer has not been verified. Open this folder in VS Code to edit it; its selected Python interpreter is `.venv\Scripts\python.exe`.

## Use the prototype

1. Add a meeting title, date, and transcript; upload a UTF-8 `.txt` transcript of up to 30,000 characters; or load one of the fictional Atlas meetings.
2. Extract a preview of decisions, action items, owners, and due dates. Review source speaker labels and correct the preview; a transcript is not an instruction to perform an external action.
3. Review warnings for missing owners or dates and conflicts with previously accepted decisions. Keep the previous decision or replace it explicitly.
4. Approve the reviewed meeting to update accepted memory. Saving meeting input alone does not approve the extracted decisions.
5. Use the in-app due-soon view, weekly digest, and owner Markdown exports to review follow-ups. Reminders include approved/published open actions only; saving a draft is not enough. Missing dates need review before reliable reminders can be calculated. These are local views and exports shown while the app is open; no unattended emails, calendar alarms, or scheduled background messages are sent.
6. For GitHub Issues, review the issue preview and target repository, then explicitly approve the external action. No issue should be posted merely by extracting or saving a meeting.

For a repeatable demo, use a reference date in ISO form (`YYYY-MM-DD`) and the two Atlas fixtures. The first proposes a launch six days after the reference date; the second proposes nine days after it. Approve the first, then inspect the second to demonstrate conflict resolution. The fixtures also contain explicit action owners/dates and incomplete follow-ups that should be reviewed.

## Voice input and accessibility

The official brief requires building with Wispr Flow and natural speech captured through Wispr Flow as the main product input. Focus the transcript field, dictate with the installed Wispr Flow app, then review the resulting text. DecisionDesk consumes that text; it does not embed or call a Wispr API and does not record audio itself.

Typing, pasting, and uploading UTF-8 `.txt` transcript text are available as an accessible fallback and for local testing. That fallback does not by itself prove compliance with the voice requirement. The user can currently type only: an organizer-approved accessibility exception or a permitted teammate's actual Wispr demonstration is still needed. No Wispr demonstration has been performed for DecisionDesk, and no accommodation is recorded.

## Extraction and AI status

The default offline extractor uses deterministic rules. It is **not live AI**, and it can miss indirect phrasing, negation, ambiguous dates, or complex decisions. Explicit speaker labels and ISO dates work best. Review every proposed owner, date, and decision before approval.

An optional local Ollama connection can use `/api/chat` with a model already installed by the user. Ollama 0.40.13 and Qwen3 1.7B are installed on this computer. A live fictional two-line meeting passed source-grounded decision/task extraction in 12.8 seconds; the selected local model preference is retained in ignored local data. Qwen3 0.6B is also installed but was not selected because it made classification mistakes. This is a basic smoke check, not a real-meeting accuracy benchmark. Compact models still need human review. Installing the OpenAI SDK during preparation did not connect a paid API; no paid request is part of this setup. The user requested free-only use. Account creation, billing, and permissions remain the user's decision.

## Storage and external actions

Meeting transcripts, reviewed decisions, and action items are stored locally in SQLite at `data/decisiondesk.sqlite3`. This includes text pasted, dictated, or uploaded into the app. Use fictional data for demos and avoid uploading confidential meeting content. The `data/` folder is excluded from Git; a local database is not a cloud backup.

GitHub integration uses the existing `gh` sign-in. The initial target is the private preparation repository:

https://github.com/devrajsengar786-sssup/product-space-hackathon-prep-2026-10-31

Changing the target or creating issues requires a preview and an explicit confirmation in the app. Only the reviewed issue title/body should be sent. Do not put API keys, personal credentials, or an entire sensitive transcript into an issue. No social post, issue, or message is authorized merely by loading the demo.

## Check the implementation

From this folder:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On **31 October 2026, all 79 automated checks passed**: 15 extraction/provider-boundary tests, 22 persistence/tracker-adapter tests, 12 workspace-feature tests, 12 assistant tests, 9 live-session tests, 3 navigation tests, and 6 Streamlit UI workflow tests. GitHub calls and Ollama responses in those tests were mocked; they do not establish a working live integration.

A local browser check also loaded the fictional planning meeting, extracted its results, and opened the review screen with source evidence and owner/date warnings. No approval was clicked in that browser check. No GitHub issue or Wispr recording was made. The later local AI smoke check used only fictional text on this computer. Full details and remaining live checks are in `PROJECT-NOTES.md`.

Tests and fictional fixtures do not establish real meeting accuracy, actual Wispr use, a working local model, or judge access to private links. Visual restyling uses a navy/teal workspace direction and is verified separately from the functional suite.

## Submission

The original generic environment check and launcher were prepared before kickoff. DecisionDesk implementation began during the hackathon at the user's request. Keep the contribution disclosure in `PROJECT-NOTES.md` accurate.

Use the official brief and submission portal for final requirements. Prepare a three-minute demo, code access for judges, a short problem/architecture explanation, and honest Wispr usage evidence or the organizer's approved accessibility accommodation. The project deadline is 31 October 2026, 11:59 PM IST; LinkedIn submission is 1 November 2026, 11:59 PM IST. The user requested localhost-only use, so no hosted demo is being published. Judge access to code/video and any later sharing changes remain the user's decision.

Official brief: https://theproductspace.in/ai-hackathon-details/problem-statement

Event details: https://theproductspace.in/ai-hackathon-details


## Professional workspace features

Search meetings, task text, owners, and decision evidence with source links. Timeline retains superseded decisions; the latest-meeting view separates draft suggestions from accepted updates. Edit task priorities, deadlines and dependencies; cyclic dependencies are rejected and blocked tasks cannot be completed. Export open deadlines as calendar events without sending invitations.

Create isolated local project workspaces from Workspace settings. Download a JSON backup and restore it only into an empty workspace; validation and rollback protect existing work. Backups include transcripts and should be kept private. Team insights report actual approved-task workload, overdue work and completion. No notifications are sent in the background. Local edits do not synchronize previously created GitHub issues.


To repeat the optional live local-model check, run `.\.venv\Scripts\python.exe verify_local_ai.py` with Ollama running and Qwen3 1.7B installed. It uses fictional text, checks extracted categories/owner/deadline, records local results under ignored `data/`, and selects the model only after passing. It does not approve a meeting or create issues. Model request format follows the [official Ollama chat API](https://docs.ollama.com/api/chat).


## AI Assistant and clearer dashboard

The dashboard prioritizes meetings needing review, open tasks, overdue tasks and completed work. Attention items link directly to review; the next-deadline view excludes overdue work, which is shown separately. Capture, Ask your meetings and Meeting brief are one click away.

AI Assistant adds six local-model tools: meeting questions, agenda briefs, missing-detail questions, editable follow-up drafts, suggested task steps and possible delivery risks. Meeting-specific tools let you select the meeting; task breakdown uses an approved open task. Missing-owner/deadline field checks are identified separately from AI output.

Answers are generated from up to ten selected excerpts within a bounded context, using simple keyword ranking and source-type diversity. This is not exhaustive semantic search. Every retained item needs a known source ID and an exact quote from the supplied source; unverifiable citations are omitted. Quotes establish where the text came from, not that an AI interpretation is correct. Draft/current/superseded statuses are shown beside citations. Sources link back to meeting review. Drafts can be edited and downloaded; no assistant tool approves meetings, creates tasks, updates memory or sends messages. Switching context hides older answers.

The automated suite includes citation rejection, scope isolation, local-provider boundaries, unchanged storage and all six UI modes. `assistant_smoke.py` exercises all six tools against fictional temporary data using the installed Qwen3 1.7B model, saving results under ignored `data/`. Run this optional check only with local Ollama available. Compact-model suggestions need human review; no production accuracy claim is made.

Risk assistance is restricted to detected source flags (overdue, incomplete, blocked or draft-conflicting work); when none exist it does not invent a risk report. Clarification filtering omits questions about known owners, dates and status. AI interpretations still require review.


Live meeting companion added: workspace-local sessions with an agenda, participant names, typed/Wispr-entered notes, an optional existing Zoom/Meet/Teams link, and start/pause/resume/finish clock controls. The clock persists across page reloads and excludes paused time; it continues counting elapsed time while running, even if the browser is closed. Notes save on field submission/blur or Save notes now. Closing the browser with unsubmitted keystrokes can lose those keystrokes. Conflicting stale-tab saves are rejected, with an option to download local edits before reloading.

Finished sessions are read-only. Use finished notes for AI review prefills Capture meeting; the user still starts analysis and reviews/approves the resulting plan. This handoff does not create tasks, approve decisions or publish anything. Live sessions use a separate ignored `.live.sqlite3` file alongside the workspace database. Export notes from the live page: the normal JSON workspace backup does not include live sessions. After analysis, the saved transcript is included in normal workspace backup. No call is created, joined or hosted by the app. No microphone/camera permissions, audio recording, automatic transcription or attendee invitations were added. Browser verification uses explicitly fictional typed notes and is not Wispr usage evidence.


Navigation simplified to seven sections: Dashboard, New meeting, Meeting memory, Tasks, AI Assistant, Reports and Settings. New meeting groups Paste transcript and Live notes; Meeting memory groups Search, Decisions, History and Review meetings; Reports groups Weekly digest and Team insights; Settings groups Workspace and Connections. Related tools render only when selected, so inactive connection controls do not change the analysis preference. Existing in-app links route to the correct section and local view. No stored meeting data, live sessions or tools were deleted. Tests cover route completeness, migration from old navigation state and review/capture/task workflows through the grouped views.


## Demo and submission preparation

See `docs/submission-pack/README.md` for the timed three-minute demo, contribution disclosure, submission draft, review-only LinkedIn drafts and genuine Wispr recording checklist. `rehearse_demo.py` optionally runs two live local-AI extractions against fictional content and seeds a separate labelled rehearsal workspace after the checks pass. It never posts issues or messages. Existing nonempty rehearsal data is preserved. Scripted fixture approval is explicitly labelled and must not be represented as a live user review or Wispr evidence.
