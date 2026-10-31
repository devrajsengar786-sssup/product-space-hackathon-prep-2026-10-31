"""Local meeting memory and approval-gated tasks for DecisionDesk.

Only approved meetings update decision memory.  Data stays in the supplied SQLite
file; the store does not make network requests.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
from .features import WorkspaceFeatures


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _day(value: str | None, *, required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            raise ValueError("A date in YYYY-MM-DD format is required.")
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("Dates must use YYYY-MM-DD format.") from exc


def _text(value: object, limit: int = 10000) -> str:
    return str(value or "").strip()[:limit]


def _key(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", _text(value)).casefold()
    return re.sub(r"[\W_]+", "", normalized)


def _value_key(value: object) -> str:
    # Keep meaningful punctuation: "1.5" and "15", or "A/B" and "AB",
    # must not accidentally compare equal.
    normalized = unicodedata.normalize("NFKC", _text(value)).casefold()
    return re.sub(r"\s+", " ", normalized).strip(" \t\r\n.,;!")


def _decision(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError("Each decision must be an object.")
    topic = _text(item.get("topic"), 300)
    statement = _text(item.get("statement"), 3000)
    if not topic or not statement:
        raise ValueError("Each decision needs a topic and statement.")
    return {
        "topic": topic,
        "statement": statement,
        "value": _text(item.get("value") or statement, 3000),
        "owner": _text(item.get("owner"), 300) or "Unassigned",
        "due_date": _day(item.get("due_date")),
        "evidence": _text(item.get("evidence"), 3000),
    }


def _action(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError("Each action must be an object.")
    title = _text(item.get("title"), 500)
    if not title:
        raise ValueError("Every action needs a title before approval.")
    return {
        "title": title,
        "owner": _text(item.get("owner"), 300) or "Unassigned",
        "due_date": _day(item.get("due_date")),
        "description": _text(item.get("description"), 6000),
        "evidence": _text(item.get("evidence"), 3000),
    }


class Store(WorkspaceFeatures):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS meetings (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    meeting_date TEXT NOT NULL,
                    analysis TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY,
                    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
                    topic TEXT NOT NULL,
                    topic_key TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    value TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    due_date TEXT,
                    evidence TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS current_decision_topic
                    ON decisions(topic_key) WHERE active = 1;
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY,
                    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
                    title TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    due_date TEXT,
                    description TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    external_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS publication_attempts (
                    action_id INTEGER PRIMARY KEY REFERENCES actions(id),
                    repository TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error TEXT
                );
            """)
            self._upgrade_features(db)

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(str(self.path), timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _meeting(row) -> dict:
        result = dict(row)
        result["analysis"] = json.loads(result["analysis"])
        return result

    @staticmethod
    def _insert_action(db, meeting_id: int, item: dict, status: str):
        now = _now()
        db.execute("""INSERT INTO actions
            (meeting_id,title,owner,due_date,description,evidence,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""", (
            meeting_id, item["title"], item["owner"], item["due_date"],
            item["description"], item["evidence"], status, now, now,
        ))

    def save_meeting(self, title: str, transcript: str, meeting_date: str, analysis: dict) -> int:
        title = _text(title, 500)
        transcript = _text(transcript, 100000)
        if not title or not transcript:
            raise ValueError("Meeting title and transcript are required.")
        if not isinstance(analysis, dict):
            raise ValueError("Analysis must be an object.")
        meeting_date = _day(meeting_date, required=True)
        clean = dict(analysis)
        clean["decisions"] = [_decision(item) for item in analysis.get("decisions", [])]
        clean["actions"] = [_action(item) for item in analysis.get("actions", [])]
        # Multiple current values for one topic are ambiguous; require a clearer
        # extraction instead of silently keeping the last value.
        topic_keys = [_key(item["topic"]) for item in clean["decisions"]]
        if len(set(topic_keys)) != len(topic_keys):
            raise ValueError("The analysis contains multiple decisions for one topic. Resolve these before saving.")
        with self._connection() as db:
            cursor = db.execute("""INSERT INTO meetings
                (title,transcript,meeting_date,analysis,status,created_at)
                VALUES (?,?,?,?,'draft',?)""", (
                title, transcript, meeting_date, json.dumps(clean, ensure_ascii=False), _now(),
            ))
            meeting_id = int(cursor.lastrowid)
            for item in clean["actions"]:
                self._insert_action(db, meeting_id, item, "draft")
        return meeting_id

    def get_meeting(self, meeting_id: int) -> dict:
        with self._connection() as db:
            row = db.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        if row is None:
            raise ValueError("Meeting not found.")
        return self._meeting(row)

    def list_meetings(self) -> list[dict]:
        with self._connection() as db:
            rows = db.execute("SELECT * FROM meetings ORDER BY meeting_date DESC,id DESC").fetchall()
        return [self._meeting(row) for row in rows]

    @staticmethod
    def _find_conflicts(db, decisions: list[dict]) -> list[dict]:
        current = {row["topic_key"]: dict(row) for row in db.execute("""
            SELECT d.*,m.title AS previous_meeting_title FROM decisions d
            JOIN meetings m ON m.id=d.meeting_id WHERE d.active=1
        """).fetchall()}
        conflicts = []
        for index, raw in enumerate(decisions):
            item = _decision(raw)
            previous = current.get(_key(item["topic"]))
            if previous and _value_key(previous["value"]) != _value_key(item["value"]):
                conflicts.append({
                    "topic": item["topic"],
                    "previous_id": previous["id"],
                    "previous_statement": previous["statement"],
                    "proposed_statement": item["statement"],
                    "previous_value": previous["value"],
                    "proposed_value": item["value"],
                    "previous_meeting_id": previous["meeting_id"],
                    "previous_meeting_title": previous["previous_meeting_title"],
                    "proposed_index": index,
                    "reason": "The proposed value differs from the currently approved decision for this topic. Review the evidence before replacing it.",
                })
        return conflicts

    def find_conflicts(self, decisions: list[dict]) -> list[dict]:
        with self._connection() as db:
            return self._find_conflicts(db, decisions)

    @staticmethod
    def _memory_version(db) -> str:
        ids = [row["id"] for row in db.execute(
            "SELECT id FROM decisions WHERE active=1 ORDER BY id"
        ).fetchall()]
        return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode("utf-8")).hexdigest()

    def memory_version(self) -> str:
        """Return an optimistic-concurrency token for current decision memory."""
        with self._connection() as db:
            return self._memory_version(db)

    def approve_meeting(
        self, meeting_id: int, actions: list[dict], resolutions: dict[str, str],
        *, decision_indices: list[int] | None = None,
        expected_memory_version: str | None = None,
    ) -> None:
        """Approve reviewed actions and only the selected extracted decisions.

        Selection and resolution keys refer to indices in the original analysis.
        An empty selection accepts no decisions; None preserves the default of
        accepting all decisions. Excluded decisions never update memory.
        Pass the version displayed during review to reject stale approvals from
        another tab or a second reviewer, including changes from empty memory.
        """
        clean_actions = [_action(item) for item in actions]
        with self._connection() as db:
            # Lock before rereading memory: two open review tabs cannot approve
            # against an obsolete conflict snapshot.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
            if row is None:
                raise ValueError("Meeting not found.")
            if expected_memory_version is not None and expected_memory_version != self._memory_version(db):
                raise ValueError("Decision memory changed. Review the latest conflicts before approving.")
            analysis = json.loads(row["analysis"])
            decisions = [_decision(item) for item in analysis.get("decisions", [])]
            if decision_indices is None:
                selected = set(range(len(decisions)))
            else:
                if not isinstance(decision_indices, list) or any(
                    type(index) is not int or index < 0 or index >= len(decisions)
                    for index in decision_indices
                ):
                    raise ValueError("Decision selection contains an invalid index.")
                if len(set(decision_indices)) != len(decision_indices):
                    raise ValueError("Decision selection contains duplicate indices.")
                selected = set(decision_indices)
            if row["status"] == "approved":
                return  # Double clicks cannot duplicate memory or reset tasks.
            conflicts = [item for item in self._find_conflicts(db, decisions)
                         if item["proposed_index"] in selected]
            conflict_indices = {item["proposed_index"] for item in conflicts}
            for item in conflicts:
                choice = resolutions.get(str(item["proposed_index"]))
                if choice not in {"keep_previous", "replace"}:
                    raise ValueError("Resolve every decision conflict before approval.")
            for index, item in enumerate(decisions):
                if index not in selected:
                    continue
                if index in conflict_indices and resolutions[str(index)] == "keep_previous":
                    continue
                old = db.execute("SELECT * FROM decisions WHERE topic_key=? AND active=1", (_key(item["topic"]),)).fetchone()
                if old and _value_key(old["value"]) == _value_key(item["value"]):
                    continue
                db.execute("UPDATE decisions SET active=0 WHERE topic_key=? AND active=1", (_key(item["topic"]),))
                db.execute("""INSERT INTO decisions
                    (meeting_id,topic,topic_key,statement,value,owner,due_date,evidence,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""", (
                    meeting_id, item["topic"], _key(item["topic"]), item["statement"],
                    item["value"], item["owner"], item["due_date"], item["evidence"], _now(),
                ))
            db.execute("DELETE FROM actions WHERE meeting_id=? AND status='draft'", (meeting_id,))
            for item in clean_actions:
                self._insert_action(db, meeting_id, item, "approved")
            analysis["actions"] = clean_actions
            analysis["approved_decision_indices"] = sorted(selected)
            analysis["decision_resolutions"] = {
                str(index): resolutions[str(index)]
                for index in conflict_indices
            }
            db.execute("UPDATE meetings SET status='approved',approved_at=?,analysis=? WHERE id=?", (_now(), json.dumps(analysis, ensure_ascii=False), meeting_id))

    def list_decisions(self) -> list[dict]:
        with self._connection() as db:
            rows = db.execute("""SELECT d.*,m.title AS meeting_title,m.meeting_date
                FROM decisions d JOIN meetings m ON m.id=d.meeting_id
                WHERE d.active=1 ORDER BY d.id DESC""").fetchall()
        return [dict(row) for row in rows]

    def list_actions(self, meeting_id: int | None = None) -> list[dict]:
        query = "SELECT a.*,m.title AS meeting_title FROM actions a JOIN meetings m ON m.id=a.meeting_id"
        params = ()
        if meeting_id is not None:
            query += " WHERE a.meeting_id=?"
            params = (meeting_id,)
        query += " ORDER BY a.id DESC"
        with self._connection() as db:
            rows = db.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_action(self, action_id: int) -> dict:
        with self._connection() as db:
            row = db.execute("SELECT a.*,m.title AS meeting_title FROM actions a JOIN meetings m ON m.id=a.meeting_id WHERE a.id=?", (action_id,)).fetchone()
        if row is None:
            raise ValueError("Action not found.")
        return dict(row)

    def update_action_status(self, action_id: int, status: str) -> None:
        if status not in {"approved", "done"}:
            raise ValueError("Use meeting approval for drafts and the tracker adapter for publishing.")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if row is None:
                raise ValueError("Action not found.")
            current = row["status"]
            if current == status:
                return
            if status == "done" and current not in {"approved", "published"}:
                raise ValueError("Only approved or published actions can be completed.")
            if status == "done" and self._unresolved_dependencies(db, action_id):
                raise ValueError("Complete this task's dependencies first.")
            if status == "approved" and current != "done":
                raise ValueError("Only completed actions can be reopened.")
            next_status = "published" if status == "approved" and row["external_url"] else status
            db.execute("UPDATE actions SET status=?,updated_at=? WHERE id=?", (next_status, _now(), action_id))
            self._event(db, 'task_status', action_id, {'before':current,'after':next_status})

    def mark_published(self, action_id: int, url: str) -> None:
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[1-9][0-9]*", url):
            raise ValueError("Tracker result must be a GitHub issue URL.")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            action = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if action is None:
                raise ValueError("Action not found.")
            if action["external_url"]:
                if action["external_url"] != url:
                    raise ValueError("This action already has a different tracker issue.")
                return
            if action["status"] != "approved":
                raise ValueError("Only approved actions can be published.")
            db.execute("UPDATE actions SET status='published',external_url=?,updated_at=? WHERE id=?", (url, _now(), action_id))
            db.execute("UPDATE publication_attempts SET state='published',finished_at=? WHERE action_id=?", (_now(), action_id))

    def claim_publication(self, action_id: int, repository: str) -> dict:
        """Reserve one posting attempt before any external request."""
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT a.*,m.title AS meeting_title FROM actions a JOIN meetings m ON m.id=a.meeting_id WHERE a.id=?", (action_id,)).fetchone()
            if row is None:
                raise ValueError("Action not found.")
            action = dict(row)
            if action["external_url"]:
                action["publication_state"] = "existing"
                return action
            if action["status"] != "approved":
                raise ValueError("Review and approve this action before posting it.")
            previous = db.execute("SELECT * FROM publication_attempts WHERE action_id=?", (action_id,)).fetchone()
            if previous:
                raise ValueError("A publication attempt is already recorded. Check GitHub and reconcile its result before retrying; no duplicate request was sent.")
            db.execute("INSERT INTO publication_attempts(action_id,repository,state,started_at) VALUES (?,?,'pending',?)", (action_id, repository, _now()))
            action["publication_state"] = "claimed"
            return action

    def fail_publication(self, action_id: int, message: str) -> None:
        with self._connection() as db:
            db.execute("UPDATE publication_attempts SET state='needs_review',finished_at=?,error=? WHERE action_id=? AND state='pending'", (_now(), _text(message, 500), action_id))

    def get_publication_attempt(self, action_id: int) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM publication_attempts WHERE action_id=?", (action_id,)).fetchone()
        return dict(row) if row else None

    def due_actions(self, as_of: str, days: int = 7) -> list[dict]:
        today = date.fromisoformat(_day(as_of, required=True))
        if not 0 <= days <= 365:
            raise ValueError("The reminder window must be between 0 and 365 days.")
        end = (today + timedelta(days=days)).isoformat()
        # Overdue items remain visible instead of disappearing after their date.
        with self._connection() as db:
            rows = db.execute("""SELECT a.*,m.title AS meeting_title FROM actions a
                JOIN meetings m ON m.id=a.meeting_id
                WHERE a.status IN ('approved','published') AND a.due_date IS NOT NULL
                AND a.due_date<=? ORDER BY a.due_date,a.id""", (end,)).fetchall()
        return [dict(row) for row in rows]

    def weekly_digest(self, as_of: str, owner: str | None = None) -> dict:
        today = date.fromisoformat(_day(as_of, required=True))
        start = today - timedelta(days=6)
        end = today + timedelta(days=7)
        grouped = {}
        for action in self.list_actions():
            if action["status"] == "draft" or (owner and action["owner"] != owner):
                continue
            if action["status"] == "done" and not (start.isoformat() <= action["updated_at"][:10] <= today.isoformat()):
                continue
            bucket = grouped.setdefault(action["owner"], {"open": [], "completed": [], "due_soon": [], "overdue": []})
            if action["status"] == "done":
                bucket["completed"].append(action)
                continue
            bucket["open"].append(action)
            due = action["due_date"]
            if due and due < today.isoformat():
                bucket["overdue"].append(action)
            elif due and due <= end.isoformat():
                bucket["due_soon"].append(action)
        return dict(sorted(grouped.items()))

    def stats(self) -> dict:
        today = date.today().isoformat()
        with self._connection() as db:
            return {
                "meetings": db.execute("SELECT COUNT(*) FROM meetings").fetchone()[0],
                "decisions": db.execute("SELECT COUNT(*) FROM decisions WHERE active=1").fetchone()[0],
                "open_actions": db.execute("SELECT COUNT(*) FROM actions WHERE status IN ('approved','published')").fetchone()[0],
                "overdue": db.execute("SELECT COUNT(*) FROM actions WHERE status IN ('approved','published') AND due_date<?", (today,)).fetchone()[0],
            }
