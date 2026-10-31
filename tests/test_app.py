"""UI workflow checks with fictional meetings and a temporary database."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from decisiondesk.store import Store
from decisiondesk.navigation import destination, VIEW_KEYS


class AppWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='decisiondesk-ui-')
        self.db = Path(self.temp.name) / 'workspace.sqlite3'
        self.env = patch.dict(os.environ, {'DECISIONDESK_DB_PATH': str(self.db)})
        self.env.start()
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=30)
        self.assert_no_exception()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def assert_no_exception(self):
        self.assertFalse(self.app.exception, str(self.app.exception))

    def button(self, label):
        return next(item for item in self.app.button if item.label == label)

    def page(self, label):
        section,view=destination(label)
        self.app.sidebar.radio[0].set_value(section).run(timeout=30)
        self.assert_no_exception()
        if section in VIEW_KEYS:
            next(w for w in self.app.radio if w.key==VIEW_KEYS[section]).set_value(view).run(timeout=30)
            self.assert_no_exception()

    def approve(self):
        checkbox = next(c for c in self.app.checkbox if c.label.startswith('I reviewed'))
        checkbox.check().run(timeout=30)
        self.button('Approve & save plan').click().run(timeout=30)
        self.assert_no_exception()

    def capture_sample(self, label):
        self.page('Capture meeting')
        self.button(label).click().run(timeout=30)
        self.button('Find decisions & actions →').click().run(timeout=30)
        self.assert_no_exception()
        self.assertEqual(self.app.sidebar.radio[0].value, 'Meeting memory')
        self.assertEqual(self.app.session_state['memory_view'],'Review meetings')

    def test_capture_approve_cross_meeting_conflict_and_follow_through(self):
        self.capture_sample('Load planning meeting')
        store = Store(self.db)
        self.assertEqual(store.list_decisions(), [])
        self.assertEqual(store.due_actions('2026-10-31'), [])
        self.approve()
        self.assertEqual(len(store.list_decisions()), 1)
        before = store.list_decisions()[0]['value']
        self.assertEqual(len([a for a in store.list_actions() if a['status']=='approved']), 2)
        self.capture_sample('Load follow-up meeting')
        self.assertTrue(any('differs' in w.value for w in self.app.warning))
        self.approve()
        self.assertTrue(any('Resolve every decision conflict' in error.value for error in self.app.error))
        self.assertEqual(store.list_decisions()[0]['value'], before)
        resolution = next(r for r in self.app.radio if r.label == 'Which decision should the workspace keep?')
        resolution.set_value('Accept this meeting’s update').run(timeout=30)
        self.button('Approve & save plan').click().run(timeout=30)
        self.assert_no_exception()
        self.assertNotEqual(store.list_decisions()[0]['value'], before)
        self.page('Action board')
        publish = self.button('Create selected GitHub Issues')
        self.assertTrue(publish.disabled)
        self.button('Mark done').click().run(timeout=30)
        self.assert_no_exception()
        self.assertEqual(len([a for a in store.list_actions() if a['status']=='done']), 1)
        for page in ['Decision memory', 'Weekly digest', 'Search memory', 'Timeline & changes', 'Team insights', 'Workspace settings', 'Connections', 'Overview']:
            self.page(page)

    def test_create_and_switch_workspace_preserves_isolation(self):
        self.capture_sample('Load planning meeting')
        self.approve()
        self.page('Workspace settings')
        next(w for w in self.app.text_input if w.label=='Workspace name').set_value('Independent project')
        self.button('Create workspace').click().run(timeout=30)
        self.assert_no_exception()
        self.assertNotEqual(self.app.sidebar.selectbox[0].value,'main')
        self.page('Action board')
        self.assertFalse(any(b.label=='Mark done' for b in self.app.button))
        self.app.sidebar.selectbox[0].set_value('main').run(timeout=30)
        self.assert_no_exception()
        self.assertTrue(any(b.label=='Mark done' for b in self.app.button))

    def test_assistant_modes_render_and_cited_answer_stays_a_draft(self):
        from decisiondesk.assistant import MODES, workspace_sources
        import json
        self.capture_sample('Load planning meeting')
        self.approve()
        store=Store(self.db)
        before=json.loads(store.export_backup())['tables']
        self.app.session_state['analysis_engine']='ollama'
        self.app.session_state['ollama_model']='test-model'
        self.page('AI Assistant')
        mode_widget=lambda: next(w for w in self.app.selectbox if w.label=='What would you like help with?')
        for mode in MODES:
            mode_widget().set_value(mode).run(timeout=30)
            self.assert_no_exception()
        mode_widget().set_value('Ask your meetings').run(timeout=30)
        source=next(s for s in workspace_sources(store) if s['id'].startswith('D'))
        response={'message':{'content':json.dumps({'items':[{'text':'The launch decision is available for review.','source_id':source['id'],'quote':source['text'][:35]}],'unanswered':''})}}
        next(w for w in self.app.text_area if w.label=='Your question').set_value('What is the launch date?')
        with patch('decisiondesk.assistant._request_json',return_value=response):
            self.button('Ask AI').click().run(timeout=30)
        self.assert_no_exception()
        self.assertTrue(any(w.label=='Edit your draft' for w in self.app.text_area))
        self.assertTrue(any(b.label=='Open source meeting →' for b in self.app.button))
        self.assertEqual(before,json.loads(store.export_backup())['tables'])
        mode_widget().set_value('Meeting brief').run(timeout=30)
        self.assertFalse(any(w.label=='Edit your draft' for w in self.app.text_area))

    def test_live_meeting_notes_finish_and_prepare_review(self):
        self.page('Live meeting')
        next(w for w in self.app.text_input if w.label=='New meeting title').set_value('Fictional live sync')
        self.button('Create live meeting').click().run(timeout=30)
        self.assert_no_exception()
        notes='Maya: Decision: launch date is 2026-11-06.'
        next(w for w in self.app.text_area if w.label=='Live meeting notes').set_value(notes).run(timeout=30)
        self.assert_no_exception()
        self.button('Start meeting').click().run(timeout=30)
        self.assert_no_exception()
        self.button('Pause meeting').click().run(timeout=30)
        self.button('Resume meeting').click().run(timeout=30)
        self.button('Finish meeting').click().run(timeout=30)
        self.assert_no_exception()
        self.assertTrue(next(w for w in self.app.text_area if w.label=='Live meeting notes').disabled)
        self.assertEqual(Store(self.db).list_meetings(),[])
        self.button('Use finished notes for AI review →').click().run(timeout=30)
        self.assert_no_exception()
        self.assertEqual(self.app.sidebar.radio[0].value,'New meeting')
        self.assertEqual(self.app.session_state['new_meeting_view'],'Paste transcript')
        self.assertTrue(any(w.value==notes for w in self.app.text_area))
        self.assertEqual(Store(self.db).list_meetings(),[])

    def test_empty_capture_keeps_user_on_form(self):
        self.page('Capture meeting')
        self.button('Find decisions & actions →').click().run(timeout=30)
        self.assert_no_exception()
        self.assertTrue(any('Add a title' in error.value for error in self.app.error))
        self.assertEqual(Store(self.db).list_meetings(), [])

    def test_posting_approval_resets_when_destination_or_tasks_change(self):
        store = Store(self.db)
        actions = [dict(title=f'Task {i}', owner='Maya', due_date='2026-11-04', description='Fictional test task', evidence='Maya: I will do this.') for i in (1,2)]
        mid = store.save_meeting('Fictional UI test', 'Maya: I will do this.', '2026-10-31',
                                 dict(summary='test', speakers=['Maya'], decisions=[], actions=actions, warnings=[], engine='offline'))
        store.approve_meeting(mid, actions, {})
        ids = [a['id'] for a in store.list_actions()]
        self.page('Action board')
        next(w for w in self.app.multiselect if w.label=='Tasks to publish').set_value([ids[0]]).run(timeout=30)
        consent = next(c for c in self.app.checkbox if c.label.startswith('I approve creating'))
        consent.check().run(timeout=30)
        self.assertFalse(self.button('Create selected GitHub Issues').disabled)
        next(w for w in self.app.text_input if w.label=='Destination repository (owner/name)').set_value('example/a-different-repository').run(timeout=30)
        consent = next(c for c in self.app.checkbox if c.label.startswith('I approve creating'))
        self.assertFalse(consent.value)
        self.assertTrue(self.button('Create selected GitHub Issues').disabled)
        consent.check().run(timeout=30)
        next(w for w in self.app.multiselect if w.label=='Tasks to publish').set_value(ids).run(timeout=30)
        consent = next(c for c in self.app.checkbox if c.label.startswith('I approve creating'))
        self.assertFalse(consent.value)
        self.assertTrue(self.button('Create selected GitHub Issues').disabled)
        self.assertFalse(any(a.get('external_url') for a in store.list_actions()))


if __name__ == '__main__':
    unittest.main()
