import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from decisiondesk.public_demo import session_database, seed_fictional_workspace
from decisiondesk.store import Store
from decisiondesk.integrations import github_status, publish_action


class PublicDemoTests(unittest.TestCase):
    def test_sessions_have_separate_data_and_stable_paths(self):
        with tempfile.TemporaryDirectory() as root:
            first, second = {}, {}
            one = session_database(first, root)
            two = session_database(second, root)
            self.assertEqual(one, session_database(first, root))
            self.assertNotEqual(one, two)
            owner = Store(Path(root) / 'owner.sqlite3')
            seed_fictional_workspace(Store(one), '2026-10-31')
            self.assertEqual(len(Store(one).list_meetings()), 2)
            self.assertEqual(Store(two).list_meetings(), [])
            self.assertEqual(owner.list_meetings(), [])
            seed_fictional_workspace(Store(one), '2026-10-31')
            self.assertEqual(len(Store(one).list_meetings()), 2)

    def test_public_mode_cannot_use_owner_github_credentials(self):
        with patch.dict(os.environ, {'DECISIONDESK_PUBLIC_DEMO': '1'}):
            with patch('decisiondesk.integrations.subprocess.run') as run:
                self.assertFalse(github_status()['available'])
                with self.assertRaisesRegex(ValueError, 'disabled'):
                    publish_action(None, 1, 'example/repository', confirmed=True)
                run.assert_not_called()

    def test_session_id_cannot_escape_root(self):
        with self.assertRaises(ValueError):
            session_database({'public_demo_id': '../owner'}, '.')
