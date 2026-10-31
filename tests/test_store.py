"""Backend checks use temporary databases and mocked GitHub calls only."""
from datetime import date, timedelta
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from decisiondesk.store import Store
from decisiondesk.integrations import github_status, issue_body, publish_action


TODAY = date.today().isoformat()


def analysis(value="2026-11-06", owner="Maya", due=TODAY):
    return {
        "summary": "A launch date was agreed and Maya will update the plan.",
        "speakers": ["Maya", "Sam"],
        "decisions": [{"topic": "Launch date", "statement": f"Launch on {value}.", "value": value, "owner": "Sam", "due_date": None, "evidence": f"Sam: We agreed to launch on {value}."}],
        "actions": [{"title": "Update the launch plan", "owner": owner, "due_date": due, "description": "Revise the team's release plan.", "evidence": "Maya: I will update the plan."}],
        "warnings": [],
        "engine": "local-rules",
    }


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "decisiondesk.db")

    def tearDown(self):
        self.temp.cleanup()

    def save(self, value="2026-11-06", **kwargs):
        result = analysis(value, **kwargs)
        meeting_id = self.store.save_meeting("Release review", "Sam: Launch Friday. Maya: I will update the plan.", TODAY, result)
        return meeting_id, result

    def approved(self, value="2026-11-06", **kwargs):
        meeting_id, result = self.save(value, **kwargs)
        self.store.approve_meeting(meeting_id, result["actions"], {})
        return meeting_id, result

    def test_drafts_do_not_change_memory_or_create_reminders(self):
        meeting_id, result = self.save()
        self.assertEqual(self.store.get_meeting(meeting_id)["analysis"], result)
        self.assertEqual(self.store.list_decisions(), [])
        self.assertEqual(self.store.due_actions(TODAY), [])
        self.assertEqual(self.store.weekly_digest(TODAY), {})
        self.assertEqual(self.store.list_actions(meeting_id)[0]["status"], "draft")
        self.assertEqual(self.store.stats()["open_actions"], 0)

    def test_conflicts_require_explicit_resolution_and_rollback(self):
        self.approved()
        meeting_id, result = self.save("2026-11-09")
        conflict = self.store.find_conflicts(result["decisions"])[0]
        self.assertEqual(conflict["proposed_index"], 0)
        self.assertEqual(conflict["previous_value"], "2026-11-06")
        self.assertEqual(conflict["previous_meeting_title"], "Release review")
        with self.assertRaisesRegex(ValueError, "Resolve every"):
            self.store.approve_meeting(meeting_id, result["actions"], {})
        self.assertEqual(self.store.get_meeting(meeting_id)["status"], "draft")
        self.assertEqual(self.store.list_actions(meeting_id)[0]["status"], "draft")
        self.assertEqual(self.store.list_decisions()[0]["value"], "2026-11-06")

    def test_keep_previous_retains_memory_and_replace_updates_history(self):
        first_id, _ = self.approved()
        second_id, result = self.save("2026-11-09")
        self.store.approve_meeting(second_id, result["actions"], {"0": "keep_previous"})
        self.assertEqual(self.store.list_decisions()[0]["meeting_id"], first_id)
        third_id, result = self.save("2026-11-10")
        self.store.approve_meeting(third_id, result["actions"], {"0": "replace"})
        self.assertEqual(len(self.store.list_decisions()), 1)
        self.assertEqual(self.store.list_decisions()[0]["value"], "2026-11-10")
        self.assertEqual(self.store.list_decisions()[0]["meeting_id"], third_id)
        self.assertEqual(len(self.store.list_meetings()), 3)

    def test_reapproval_is_idempotent_and_does_not_reset_published_task(self):
        meeting_id, result = self.approved()
        action = self.store.list_actions(meeting_id)[0]
        self.store.mark_published(action["id"], "https://github.com/example/project/issues/1")
        self.store.approve_meeting(meeting_id, result["actions"], {})
        actions = self.store.list_actions(meeting_id)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["id"], action["id"])
        self.assertEqual(actions[0]["status"], "published")
        self.assertEqual(len(self.store.list_decisions()), 1)

    def test_exact_repeats_and_cosmetic_topic_case_do_not_conflict(self):
        self.approved()
        proposed = analysis()["decisions"]
        proposed[0]["topic"] = " LAUNCH-date "
        self.assertEqual(self.store.find_conflicts(proposed), [])
        self.assertEqual(len(self.store.list_decisions()), 1)

    def test_values_preserve_decimal_and_slash_distinctions(self):
        self.approved("1.5")
        self.assertEqual(len(self.store.find_conflicts(analysis("15")["decisions"])), 1)

    def test_excluded_decisions_never_conflict_or_change_memory(self):
        self.approved()
        result = analysis("2026-11-09")
        result["decisions"].append({"topic": "Database", "statement": "Use SQLite.", "value": "SQLite", "owner": "Maya", "due_date": None, "evidence": "Maya: We will use SQLite."})
        meeting_id = self.store.save_meeting("Second review", "Launch Monday. Use SQLite.", TODAY, result)
        # The conflicting original index 0 was unchecked; it needs no resolution.
        self.store.approve_meeting(meeting_id, result["actions"], {}, decision_indices=[1])
        current = {item["topic"]: item["value"] for item in self.store.list_decisions()}
        self.assertEqual(current, {"Launch date": "2026-11-06", "Database": "SQLite"})
        self.assertEqual(self.store.get_meeting(meeting_id)["analysis"]["approved_decision_indices"], [1])

    def test_selected_conflict_uses_original_index_and_empty_selection_is_valid(self):
        self.approved()
        result = analysis("2026-11-09")
        result["decisions"].insert(0, {"topic": "Database", "statement": "Use SQLite.", "value": "SQLite", "owner": "Maya", "due_date": None, "evidence": "SQLite."})
        meeting_id = self.store.save_meeting("Review", "Launch Monday.", TODAY, result)
        with self.assertRaisesRegex(ValueError, "Resolve every"):
            self.store.approve_meeting(meeting_id, result["actions"], {"0": "replace"}, decision_indices=[1])
        self.store.approve_meeting(meeting_id, result["actions"], {"1": "keep_previous"}, decision_indices=[1])
        self.assertEqual(len(self.store.list_decisions()), 1)
        next_id, result = self.save("2026-11-12")
        self.store.approve_meeting(next_id, result["actions"], {}, decision_indices=[])
        self.assertEqual(self.store.list_decisions()[0]["value"], "2026-11-06")

    def test_invalid_and_duplicate_selected_indices_are_rejected(self):
        meeting_id, result = self.save()
        for selected in ([-1], [1], [True], ["0"], [0, 0], "0"):
            with self.subTest(selected=selected), self.assertRaisesRegex(ValueError, "Decision selection"):
                self.store.approve_meeting(meeting_id, result["actions"], {}, decision_indices=selected)
        self.assertEqual(self.store.get_meeting(meeting_id)["status"], "draft")
        self.assertEqual(self.store.list_decisions(), [])

    def test_memory_version_is_shared_stable_and_changes_with_accepted_decisions(self):
        other_tab = Store(self.store.path)
        empty_version = self.store.memory_version()
        self.assertEqual(len(empty_version), 64)
        self.assertEqual(empty_version, other_tab.memory_version())
        draft_id, result = self.save()
        self.assertEqual(self.store.memory_version(), empty_version)
        self.store.approve_meeting(draft_id, result["actions"], {}, expected_memory_version=empty_version)
        accepted_version = self.store.memory_version()
        self.assertNotEqual(accepted_version, empty_version)
        self.assertEqual(accepted_version, other_tab.memory_version())

    def test_empty_memory_race_rejects_stale_approval_without_writes(self):
        draft_id, result = self.save("2026-11-06")
        preview_version = self.store.memory_version()
        other_tab = Store(self.store.path)
        other_result = analysis("2026-11-09")
        other_id = other_tab.save_meeting("Another tab", "Launch Monday.", TODAY, other_result)
        other_tab.approve_meeting(other_id, other_result["actions"], {}, expected_memory_version=preview_version)
        with self.assertRaisesRegex(ValueError, "Decision memory changed. Review the latest conflicts before approving"):
            self.store.approve_meeting(draft_id, result["actions"], {}, expected_memory_version=preview_version)
        self.assertEqual(self.store.get_meeting(draft_id)["status"], "draft")
        self.assertEqual(self.store.list_actions(draft_id)[0]["status"], "draft")
        self.assertEqual(self.store.list_decisions()[0]["value"], "2026-11-09")

    def test_existing_memory_race_cannot_reuse_old_conflict_confirmation(self):
        self.approved("2026-11-06")
        draft_id, result = self.save("2026-11-09")
        preview_version = self.store.memory_version()
        other_tab = Store(self.store.path)
        other_result = analysis("2026-11-10")
        other_id = other_tab.save_meeting("Another tab", "Launch Tuesday.", TODAY, other_result)
        other_tab.approve_meeting(other_id, other_result["actions"], {"0": "replace"}, expected_memory_version=preview_version)
        with self.assertRaisesRegex(ValueError, "Decision memory changed"):
            self.store.approve_meeting(draft_id, result["actions"], {"0": "replace"}, expected_memory_version=preview_version)
        self.assertEqual(self.store.list_decisions()[0]["value"], "2026-11-10")
        self.assertEqual(self.store.get_meeting(draft_id)["status"], "draft")
        # A fresh review can deliberately confirm the updated conflict.
        current_version = self.store.memory_version()
        self.store.approve_meeting(draft_id, result["actions"], {"0": "replace"}, expected_memory_version=current_version)
        self.assertEqual(self.store.list_decisions()[0]["value"], "2026-11-09")
        self.assertNotEqual(self.store.memory_version(), current_version)

    def test_multiple_draft_decisions_for_one_topic_are_rejected(self):
        result = analysis()
        result["decisions"].append(dict(result["decisions"][0], value="another date"))
        with self.assertRaisesRegex(ValueError, "multiple decisions"):
            self.store.save_meeting("Confused meeting", "Two incompatible dates", TODAY, result)
        self.assertEqual(self.store.list_meetings(), [])

    def test_invalid_date_and_empty_action_roll_back(self):
        meeting_id, result = self.save()
        invalid = [dict(result["actions"][0], due_date="nextish week")]
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            self.store.approve_meeting(meeting_id, invalid, {})
        with self.assertRaisesRegex(ValueError, "needs a title"):
            self.store.approve_meeting(meeting_id, [dict(result["actions"][0], title="")], {})
        self.assertEqual(self.store.get_meeting(meeting_id)["status"], "draft")

    def test_due_dates_digest_completion_and_reopening(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.approved(owner="Maya", due=yesterday)
        second_id, _ = self.approved(owner="Sam", due=tomorrow)
        due = self.store.due_actions(TODAY)
        self.assertEqual(len(due), 2)
        self.assertEqual(due[0]["due_date"], yesterday)
        digest = self.store.weekly_digest(TODAY)
        self.assertEqual(len(digest["Maya"]["overdue"]), 1)
        self.assertEqual(len(digest["Sam"]["due_soon"]), 1)
        self.assertEqual(list(self.store.weekly_digest(TODAY, "Sam")), ["Sam"])
        action = self.store.list_actions(second_id)[0]
        self.store.update_action_status(action["id"], "done")
        self.assertEqual(len(self.store.weekly_digest(TODAY)["Sam"]["completed"]), 1)
        self.assertEqual(self.store.stats()["open_actions"], 1)
        self.assertEqual(self.store.stats()["overdue"], 1)
        self.store.update_action_status(action["id"], "approved")
        self.assertEqual(self.store.get_action(action["id"])["status"], "approved")

    def test_draft_cannot_be_completed_or_published_directly(self):
        meeting_id, _ = self.save()
        action_id = self.store.list_actions(meeting_id)[0]["id"]
        with self.assertRaises(ValueError):
            self.store.update_action_status(action_id, "done")
        with self.assertRaises(ValueError):
            self.store.mark_published(action_id, "https://github.com/example/project/issues/1")

    def test_historical_digest_excludes_future_and_older_completions(self):
        ids = []
        for owner in ("Old completion", "Inside window", "Future completion"):
            meeting_id, _ = self.approved(owner=owner)
            action_id = self.store.list_actions(meeting_id)[0]["id"]
            self.store.update_action_status(action_id, "done")
            ids.append(action_id)
        with self.store._connection() as db:
            for action_id, completed in zip(ids, ("2026-10-24", "2026-10-29", "2026-11-01")):
                db.execute("UPDATE actions SET updated_at=? WHERE id=?", (completed + "T12:00:00+00:00", action_id))
        digest = self.store.weekly_digest("2026-10-31")
        self.assertEqual(list(digest), ["Inside window"])
        self.assertEqual(len(digest["Inside window"]["completed"]), 1)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "decisiondesk.db")
        result = analysis()
        self.meeting_id = self.store.save_meeting("Demo", "Maya: I will update the plan.", TODAY, result)
        self.store.approve_meeting(self.meeting_id, result["actions"], {})
        self.action_id = self.store.list_actions(self.meeting_id)[0]["id"]

    def tearDown(self):
        self.temp.cleanup()

    @patch("decisiondesk.integrations.subprocess.run")
    def test_unconfirmed_invalid_destination_and_draft_never_post(self, run):
        with self.assertRaises(ValueError):
            publish_action(self.store, self.action_id, "example/project")
        with self.assertRaises(ValueError):
            publish_action(self.store, self.action_id, "https://github.com/example/project", confirmed=True)
        run.assert_not_called()
        result = analysis()
        draft_id = self.store.save_meeting("Draft", "Maya: draft action", TODAY, result)
        draft_action = self.store.list_actions(draft_id)[0]["id"]
        with patch("decisiondesk.integrations.shutil.which", return_value="gh"):
            with self.assertRaises(ValueError):
                publish_action(self.store, draft_action, "example/project", confirmed=True)
        run.assert_not_called()

    @patch("decisiondesk.integrations.shutil.which", return_value="gh")
    @patch("decisiondesk.integrations.subprocess.run")
    def test_post_uses_body_file_and_is_idempotent(self, run, which):
        def create_issue(args, **kwargs):
            body_path = Path(args[args.index("--body-file") + 1])
            self.assertTrue(body_path.exists())
            body = body_path.read_text(encoding="utf-8")
            self.assertEqual(body, issue_body(self.store.get_action(self.action_id)))
            self.assertIn("Maya", body)
            self.assertIn(f"{self.meeting_id}-{self.action_id}", body)
            self.assertNotIn("shell", kwargs)
            return subprocess.CompletedProcess(args, 0, "https://github.com/example/project/issues/12\n", "")
        run.side_effect = create_issue
        url = publish_action(self.store, self.action_id, "example/project", confirmed=True)
        self.assertEqual(url, "https://github.com/example/project/issues/12")
        self.assertEqual(self.store.get_action(self.action_id)["status"], "published")
        self.assertEqual(self.store.get_publication_attempt(self.action_id)["state"], "published")
        self.assertEqual(publish_action(self.store, self.action_id, "example/project", confirmed=True), url)
        self.assertEqual(run.call_count, 1)

    @patch("decisiondesk.integrations.shutil.which", return_value="gh")
    @patch("decisiondesk.integrations.subprocess.run")
    def test_timeout_is_not_retried_and_never_exposes_stderr(self, run, which):
        run.side_effect = subprocess.TimeoutExpired("gh", 45, stderr="private-token-like-value")
        with self.assertRaisesRegex(RuntimeError, "no automatic retry") as error:
            publish_action(self.store, self.action_id, "example/project", confirmed=True)
        self.assertNotIn("private-token", str(error.exception))
        self.assertEqual(self.store.get_action(self.action_id)["status"], "approved")
        self.assertEqual(self.store.get_publication_attempt(self.action_id)["state"], "needs_review")
        with self.assertRaisesRegex(ValueError, "already recorded"):
            publish_action(self.store, self.action_id, "example/project", confirmed=True)
        self.assertEqual(run.call_count, 1)

    @patch("decisiondesk.integrations.shutil.which", return_value="gh")
    @patch("decisiondesk.integrations.subprocess.run")
    def test_unexpected_issue_url_is_not_trusted(self, run, which):
        run.return_value = subprocess.CompletedProcess([], 0, "https://github.com/other/repository/issues/99", "")
        with self.assertRaises(RuntimeError):
            publish_action(self.store, self.action_id, "example/project", confirmed=True)
        self.assertIsNone(self.store.get_action(self.action_id)["external_url"])

    @patch("decisiondesk.integrations.shutil.which", return_value=None)
    @patch("decisiondesk.integrations.subprocess.run")
    def test_no_cli_is_reported_without_calls(self, run, which):
        self.assertFalse(github_status()["available"])
        with self.assertRaisesRegex(RuntimeError, "not installed"):
            publish_action(self.store, self.action_id, "example/project", confirmed=True)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
