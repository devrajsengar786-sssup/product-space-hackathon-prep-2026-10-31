# Product Space hackathon starter

This is a pre-event installation check, not a competition solution. No API calls are implemented.

This PC's project environment reuses its existing installed Python packages (`system-site-packages`) to avoid a large redundant download. New project packages install into `.venv`; existing global packages are unchanged. A fresh machine should use the fully isolated recreation steps below.

## Start

Double-click **Start app.cmd**. It starts the app and opens http://127.0.0.1:8501 in your default browser. If a Streamlit server is already running there, it reuses that server. When this launcher starts the server, keep its window open; press Ctrl+C to stop it. After a computer restart, use the launcher again.

To edit: open this folder in VS Code. The configured interpreter is `.venv\Scripts\python.exe`.

To recreate the environment on another computer, run in this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

## AI environment

The user selected **free preparation only**. No paid API is connected and this app sends no AI requests. The OpenAI SDK and dotenv are installed as optional tools, not an event requirement. Choose a provider after kickoff, based on organizer access or an existing free account. No account, key, billing, or model access has been configured or tested.

If you later authorize API use, obtain a key directly from your provider, copy `.env.example` to `.env`, and enter the key locally. Choose an available model in `OPENAI_MODEL`. Keep `.env` private. This app only reports whether a key is present; it never displays it or sends requests. Review provider pricing and limits before authorizing a live test.

Official API setup: https://developers.openai.com/api/docs/quickstart

## Repository

This folder is a Git repository. `.env`, the environment folder, logs, and Streamlit secrets are excluded. Keep the starter repository private until you decide what access the judges require. This generic template was prepared before kickoff; document all competition contributions after kickoff.

`requirements-lock.txt` records the installed versions used for the passing local checks. A fresh isolated installation on another computer has not been tested.
