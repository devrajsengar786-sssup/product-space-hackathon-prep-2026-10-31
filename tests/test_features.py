import json
from pathlib import Path
import tempfile
import unittest
from decisiondesk.store import Store
from decisiondesk.features import calendar_export
from decisiondesk.workspaces import Workspaces
from test_store import analysis

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'main.sqlite3'
        self.store=Store(self.path)
    def tearDown(self):
        self.temp.cleanup()
    def approved(self,value='2026-11-06'):
        result=analysis(value,due='2026-11-04')
        mid=self.store.save_meeting('Release review','Maya: I will update the launch plan.','2026-10-31',result)
        self.store.approve_meeting(mid,result['actions'],{'0':'replace'})
        return self.store.list_actions(mid)[0]
    def edit(self,a,dependencies=(),priority='High'):
        self.store.edit_action(a['id'],title=a['title'],owner=a['owner'],due_date=a['due_date'],description=a['description'],priority=priority,dependencies=dependencies)
    def test_blocked_completion_and_dependency_resolution(self):
        first=self.approved();second=self.approved()
        self.edit(second,[first['id']])
        self.assertEqual(self.store.get_action(second['id'])['priority'],'High')
        with self.assertRaises(ValueError):self.store.update_action_status(second['id'],'done')
        self.assertEqual(self.store.analytics('2026-11-10')['blocked'],1)
        self.store.update_action_status(first['id'],'done')
        self.store.update_action_status(second['id'],'done')
        self.assertEqual(self.store.analytics('2026-11-10')['completed'],2)
    def test_cycles_rejected_without_mutating_saved_task(self):
        a=self.approved();b=self.approved();self.edit(b,[a['id']])
        with self.assertRaisesRegex(ValueError,'cycle'):self.edit(a,[b['id']])
        self.assertEqual(self.store.decorate_actions([a])[0]['dependencies'],[])
    def test_draft_dependency_and_invalid_priority_rejected(self):
        a=self.approved();r=analysis();mid=self.store.save_meeting('Draft','test','2026-10-31',r)
        draft=self.store.list_actions(mid)[0]
        with self.assertRaises(ValueError):self.edit(a,[draft['id']])
        with self.assertRaises(ValueError):self.edit(a,priority='Impossible')
    def test_timeline_preserves_source_and_previous_value(self):
        self.approved();self.approved('2026-11-09')
        history=self.store.decision_timeline()
        self.assertEqual(history[0]['previous_value'],'2026-11-06')
        self.assertEqual(history[0]['meeting_title'],'Release review')
        self.assertEqual([r['active'] for r in history],[1,0])
    def test_search_supports_record_types_and_literal_query(self):
        self.approved()
        self.assertEqual(self.store.search('a'),[])
        self.assertEqual(self.store.search('%'),[])
        self.assertEqual(len(self.store.search('Maya','Tasks')),1)
        self.assertEqual(len(self.store.search('release','Meetings')),1)
    def test_analytics_excludes_drafts(self):
        self.approved();self.store.save_meeting('Draft','test','2026-10-31',analysis())
        report=self.store.analytics('2026-11-10')
        self.assertEqual(report['total'],1)
        self.assertEqual(report['people'][0]['Overdue'],1)
    def test_changes_references_latest_meeting(self):
        a=self.approved();self.store.update_action_status(a['id'],'done')
        report=self.store.changes_since_last_meeting()
        self.assertEqual(report['meeting']['id'],a['meeting_id'])
        self.assertEqual(len(report['completed']),1)
    def test_calendar_escape_folding_and_only_open_approved(self):
        a=self.approved();a['title']='é'*90+'; test, next';a['description']='First\nSecond'
        output=calendar_export([a,dict(a,id=999,status='draft'),dict(a,id=998,status='done')])
        self.assertEqual(output.count('BEGIN:VEVENT'),1)
        self.assertIn('DTSTART;VALUE=DATE:20261104',output)
        self.assertIn('DTEND;VALUE=DATE:20261105',output)
        self.assertIn('\\; test\\, next',output.replace('\r\n ',''))
        self.assertIn('First\\nSecond',output)
        self.assertTrue(all(len(line.encode())<=74 for line in output.split('\r\n')))
        self.assertEqual(next(l for l in output.splitlines() if l.startswith('UID:')),next(l for l in calendar_export([a]).splitlines() if l.startswith('UID:')))
    def test_backup_roundtrip_preserves_history_dependencies_and_external_urls(self):
        a=self.approved();b=self.approved('2026-11-09');self.edit(b,[a['id']])
        self.store.mark_published(a['id'],'https://github.com/example/project/issues/1')
        other=Store(Path(self.temp.name)/'restored.sqlite3');other.restore_backup(self.store.export_backup())
        self.assertEqual(json.loads(other.export_backup())['tables'],json.loads(self.store.export_backup())['tables'])
        with self.assertRaisesRegex(ValueError,'empty'):other.restore_backup(self.store.export_backup())
    def test_bad_backup_rolls_back_all_tables(self):
        self.approved();data=json.loads(self.store.export_backup());data['tables']['actions'][0]['due_date']='invalid'
        other=Store(Path(self.temp.name)/'bad.sqlite3')
        with self.assertRaises(ValueError):other.restore_backup(json.dumps(data))
        self.assertEqual(other.list_meetings(),[])
    def test_backup_rejects_invalid_analysis_and_cycles(self):
        a=self.approved();b=self.approved();base=json.loads(self.store.export_backup())
        for mutate in ('analysis','cycle'):
            data=json.loads(json.dumps(base))
            if mutate=='analysis':data['tables']['meetings'][0]['analysis']='{"summary": []}'
            else:data['tables']['dependencies']=[{'action_id':a['id'],'depends_on':b['id']},{'action_id':b['id'],'depends_on':a['id']}]
            other=Store(Path(self.temp.name)/(mutate+'.sqlite3'))
            with self.assertRaises(ValueError):other.restore_backup(json.dumps(data))
            self.assertEqual(other.list_meetings(),[])
    def test_workspace_isolation_and_path_validation(self):
        self.approved();catalog=Workspaces(self.path);wid=catalog.create('Product launch')
        self.assertEqual(Store(catalog.path(wid)).list_meetings(),[])
        self.assertEqual(catalog.path('main'),self.path)
        with self.assertRaises(ValueError):catalog.path('../../escape')
        with self.assertRaises(ValueError):catalog.create('PRODUCT LAUNCH')

if __name__=='__main__':unittest.main()
