"""Approval-gated GitHub Issues adapter using the existing gh sign-in.

No OAuth tokens or API keys are read, printed, or copied by this module.
"""
from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile


REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")


def github_status() -> dict:
    executable = shutil.which("gh")
    if not executable:
        return {"available": False, "message": "GitHub CLI is not installed. Local review and tracking still work."}
    try:
        result = subprocess.run([executable, "auth", "status", "--hostname", "github.com"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "message": "GitHub sign-in could not be checked. Check your connection and GitHub CLI sign-in."}
    if result.returncode:
        return {"available": False, "message": "GitHub CLI needs a working sign-in and connection. No account changes were made."}
    return {"available": True, "message": "GitHub CLI sign-in is available. Task creation still requires explicit confirmation."}


def issue_body(action: dict) -> str:
    """Return the exact Markdown body that publishing will send to GitHub.

    The UI should display this verbatim, along with the title and repository,
    before collecting consent. Transcript evidence is included in this body.
    """
    return "\n".join([
        "## Approved meeting action",
        "",
        action.get("description") or action["title"],
        "",
        f"**Owner:** {action['owner']}",
        f"**Due date:** {action.get('due_date') or 'Not specified'}",
        f"**Meeting:** {action.get('meeting_title') or action['meeting_id']}",
        "",
        "### Supporting transcript excerpt",
        action.get("evidence") or "No excerpt supplied; reviewed by the user.",
        "",
        f"DecisionDesk action reference: {action['meeting_id']}-{action['id']}",
        "Created only after review and explicit posting approval.",
    ])


def publish_action(store, action_id: int, repository: str, confirmed: bool = False) -> str:
    """Create at most one issue for an approved action after explicit consent.

    A failed/timed-out request is not automatically repeated: GitHub may have
    created the issue even when its response was lost. Check the repository and
    reconcile the existing issue with Store.mark_published before retrying.
    """
    if confirmed is not True:
        raise ValueError("Confirm the destination and approve posting this action first.")
    repository = str(repository).strip()
    if not REPOSITORY.fullmatch(repository) or ".." in repository:
        raise ValueError("Use a GitHub repository in owner/name format.")
    executable = shutil.which("gh")
    if not executable:
        raise RuntimeError("GitHub CLI is not installed. No task was posted.")
    action = store.claim_publication(action_id, repository)
    if action["publication_state"] == "existing":
        return action["external_url"]
    body = issue_body(action)
    try:
        # Structured process arguments avoid shell interpretation; multiline
        # content stays in a temporary UTF-8 body file, not command arguments.
        with tempfile.TemporaryDirectory(prefix="decisiondesk-issue-") as folder:
            body_path = Path(folder) / "body.md"
            body_path.write_text(body, encoding="utf-8")
            result = subprocess.run([
                executable, "issue", "create", "--repo", repository,
                "--title", action["title"], "--body-file", str(body_path),
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
        expected = re.compile(r"https://github\.com/" + re.escape(repository) + r"/issues/[1-9][0-9]*", re.IGNORECASE)
        urls = expected.findall(result.stdout or "")
        if result.returncode != 0 or not urls:
            raise RuntimeError("GitHub did not return a confirmed issue URL. Inspect the repository before retrying.")
        url = urls[-1]
        store.mark_published(action_id, url)
        return url
    except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError) as exc:
        message = "Task posting could not be confirmed. Inspect GitHub for this action reference before retrying; no automatic retry was sent."
        store.fail_publication(action_id, message)
        raise RuntimeError(message) from exc
