# DecisionDesk

DecisionDesk is a hackathon prototype for Problem 3: turn meeting notes into reviewable decisions and action items, keep accepted memory across meetings, and flag changes before updating that memory. The included Atlas meetings are fictional. The user requested **localhost-only operation**; no hosted deployment is part of this project.

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

An optional local Ollama connection can use `/api/chat` with a model already installed by the user. No Ollama model has been installed or connected for this project. Local AI readiness and output quality are therefore unverified. Installing the OpenAI SDK during preparation did not connect a paid API; no paid request is part of this setup. The user requested free-only use. Account creation, billing, and permissions remain the user's decision.

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

On **31 October 2026, all 39 automated checks passed**: 14 extraction/provider-boundary tests, 22 persistence/tracker-adapter tests, and 3 Streamlit UI workflow tests. GitHub calls and Ollama responses in those tests were mocked; they do not establish a working live integration.

A local browser check also loaded the fictional planning meeting, extracted its results, and opened the review screen with source evidence and owner/date warnings. No approval was clicked in that browser check. No GitHub issue, AI request, or Wispr recording was made during verification. Full details and remaining live checks are in `PROJECT-NOTES.md`.

Tests and fictional fixtures do not establish real meeting accuracy, actual Wispr use, a working local model, or judge access to private links. Visual restyling uses a navy/teal workspace direction and is verified separately from the functional suite.

## Submission

The original generic environment check and launcher were prepared before kickoff. DecisionDesk implementation began during the hackathon at the user's request. Keep the contribution disclosure in `PROJECT-NOTES.md` accurate.

Use the official brief and submission portal for final requirements. Prepare a three-minute demo, code access for judges, a short problem/architecture explanation, and honest Wispr usage evidence or the organizer's approved accessibility accommodation. The project deadline is 31 October 2026, 11:59 PM IST; LinkedIn submission is 1 November 2026, 11:59 PM IST. The user requested localhost-only use, so no hosted demo is being published. Judge access to code/video and any later sharing changes remain the user's decision.

Official brief: https://theproductspace.in/ai-hackathon-details/problem-statement

Event details: https://theproductspace.in/ai-hackathon-details
