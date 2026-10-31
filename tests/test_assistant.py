import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from decisiondesk.assistant import MODES, assist, workspace_sources, select_sources, clarify_tasks, fingerprint, export_answer
from decisiondesk.analysis import AnalysisError
from decisiondesk.store import Store
from test_store import analysis

class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'data.sqlite3')
        self.analysis=analysis(due='2026-11-04')
        self.mid=self.store.save_meeting('Release review','Maya: I will update the plan.','2026-10-31',self.analysis)
    def tearDown(self):self.temp.cleanup()
    def response(self,source,**changes):
        item=dict(text='Review the plan before launch.',source_id=source['id'],quote=source['text'][:35]);item.update(changes)
        return {'message':{'content':json.dumps({'items':[item],'unanswered':''})}}
    def test_drafts_and_history_have_explicit_statuses(self):
        sources=workspace_sources(self.store)
        self.assertTrue(any(s['status']=='Draft task' for s in sources))
        self.assertFalse(any(s['id'].startswith('D') for s in sources))
        self.store.approve_meeting(self.mid,self.analysis['actions'],{})
        self.assertTrue(any(s['status']=='Current accepted decision' for s in workspace_sources(self.store)))
    def test_each_mode_is_local_read_only_and_cited(self):
        source=workspace_sources(self.store)[0];before=self.store.export_backup()
        for mode in MODES:
            with self.subTest(mode=mode),patch('decisiondesk.assistant._request_json',return_value=self.response(source,**({'text':'What acceptance criteria should the plan meet?'} if mode=='Clarify missing details' else {}))) as request:
                result=assist(mode,'Help prepare',[source],model='qwen3:1.7b',as_of='2026-10-31')
                self.assertEqual(len(result['items']),1)
                self.assertEqual(request.call_args.args[0],'http://127.0.0.1:11434/api/chat')
                self.assertFalse(request.call_args.args[1]['think'])
                self.assertIn(source['id'],export_answer(result))
        self.assertEqual(json.loads(before)['tables'],json.loads(self.store.export_backup())['tables'])
    def test_missing_or_invented_citations_are_omitted(self):
        source=workspace_sources(self.store)[0]
        for changes in ({'source_id':'other'},{'quote':'invented quote that never occurred'},{'quote':'Maya'}):
            with patch('decisiondesk.assistant._request_json',return_value=self.response(source,**changes)):
                result=assist('Ask your meetings','What changed?',[source],model='local')
                self.assertEqual(result['items'],[]);self.assertEqual(result['omitted'],1)
    def test_invalid_response_and_connection_failure_are_clear_errors(self):
        source=workspace_sources(self.store)[0]
        for response in ({},{'message':{'content':'not json'}},{'message':{'content':'[]'}}):
            with patch('decisiondesk.assistant._request_json',return_value=response):
                with self.assertRaises(AnalysisError):assist('Meeting brief','Prepare',[source],model='local')
        with patch('decisiondesk.assistant._request_json',side_effect=URLError('failure')):
            with self.assertRaisesRegex(AnalysisError,'could not finish'):assist('Meeting brief','Prepare',[source],model='local')
    def test_remote_endpoint_empty_context_and_invalid_mode_do_not_call_provider(self):
        source=workspace_sources(self.store)[0]
        with patch('decisiondesk.assistant._request_json') as request:
            for kwargs in ({'mode':'invalid','sources':[source]}, {'mode':'Meeting brief','sources':[]}, {'mode':'Meeting brief','sources':[source],'base_url':'https://example.com'}):
                with self.assertRaises(AnalysisError):assist(query='Help',model='local',**kwargs)
            request.assert_not_called()
    def test_selection_is_bounded_scoped_and_task_specific(self):
        second=self.store.save_meeting('Other project discussion','Sam: Separate meeting.','2026-11-01',analysis())
        sources=workspace_sources(self.store)
        chosen=select_sources(sources,'plan','Follow-up draft',meeting_id=self.mid)
        self.assertTrue(chosen);self.assertTrue(all(s['meeting_id']==self.mid for s in chosen))
        action=self.store.list_actions(self.mid)[0]
        chosen=select_sources(sources,'plan','Break down a task',task_id=action['id'])
        self.assertEqual([s['id'] for s in chosen],['T'+str(action['id'])])
        self.assertEqual(select_sources(sources,'','Meeting brief',budget=1),[])
        self.assertLessEqual(len(select_sources(sources*30,'','Meeting brief')),10)
    def test_changed_task_invalidates_result_fingerprint(self):
        before=fingerprint(workspace_sources(self.store));self.store.approve_meeting(self.mid,self.analysis['actions'],{})
        self.assertNotEqual(before,fingerprint(workspace_sources(self.store)))
    def test_separate_workspace_has_no_sources(self):
        other=Store(Path(self.temp.name)/'other.sqlite3');self.assertEqual(workspace_sources(other),[])
    def test_risk_context_contains_only_detected_flags(self):
        sources=workspace_sources(self.store)
        self.assertEqual(select_sources(sources,'risks','Risk suggestions'),[])
        self.store.approve_meeting(self.mid,self.analysis['actions'],{})
        action=self.store.list_actions()[0]
        self.store.edit_action(action['id'],title=action['title'],owner='Maya',due_date='2020-01-01',description='Update plan')
        selected=select_sources(workspace_sources(self.store),'risks','Risk suggestions')
        self.assertTrue(selected)
        self.assertTrue(all(s['text'].startswith('Risk flag: Overdue open task') for s in selected))
        self.assertFalse(any(s['id'].startswith('R') for s in select_sources(workspace_sources(self.store),'plan','Meeting brief')))

    def test_clarification_does_not_reask_known_owner_date_or_status(self):
        source=next(s for s in workspace_sources(self.store) if s['id'].startswith('T'))
        for question in ('What is the deadline?', 'Who is responsible?', 'What is the task status?'):
            with patch('decisiondesk.assistant._request_json',return_value=self.response(source,text=question)):
                result=assist('Clarify missing details','Check gaps',[source],model='local')
                self.assertEqual(result['items'],[])
        with patch('decisiondesk.assistant._request_json',return_value=self.response(source,text='What should the demo demonstrate?')):
            self.assertEqual(len(assist('Clarify missing details','Check gaps',[source],model='local')['items']),1)

    def test_missing_owner_statement_becomes_a_clear_question(self):
        source=dict(id='T1',meeting_id=self.mid,title='Check launch',status='Draft task',text='Owner: Unassigned\nDeadline: Missing\nSource quote: Maya: Check launch.')
        with patch('decisiondesk.assistant._request_json',return_value=self.response(source,text='Owner: Unassigned')):
            result=assist('Clarify missing details','Find gaps',[source],model='local')
        self.assertTrue(result['items'][0]['text'].startswith('Who should own'))
        self.assertTrue(result['items'][0]['text'].endswith('?'))

    def test_clarifications_identify_only_unfinished_missing_fields(self):
        base=dict(id=1,meeting_id=1,title='Check release',owner='Unassigned',due_date=None,status='draft')
        self.assertEqual(len(clarify_tasks([base])),2)
        self.assertEqual(clarify_tasks([dict(base,status='done')]),[])
        self.assertEqual(clarify_tasks([dict(base,owner='Maya',due_date='2026-11-04')]),[])

if __name__=='__main__':unittest.main()
