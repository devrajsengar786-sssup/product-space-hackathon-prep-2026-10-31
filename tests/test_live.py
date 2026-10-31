from pathlib import Path
import tempfile
import unittest
from decisiondesk.live import LiveMeetings,elapsed,export_notes,call_url

class LiveMeetingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'live.sqlite3';self.live=LiveMeetings(self.path);self.sid=self.live.create('Product sync','2026-10-31')
    def tearDown(self):self.temp.cleanup()
    def fields(self,**changes):
        result=dict(title='Product sync',agenda='Review launch',participants='Maya, Arjun',notes='Maya: Decision: launch date is 2026-11-06.',call_url='');result.update(changes);return result
    def test_clock_start_pause_resume_finish_and_reopen_storage(self):
        row=self.live.transition(self.sid,1,'start',now=100)
        self.assertEqual(elapsed(row,130),30)
        row=self.live.transition(self.sid,row['version'],'pause',now=140)
        self.assertEqual(elapsed(row,500),40)
        row=self.live.transition(self.sid,row['version'],'resume',now=600)
        reopened=LiveMeetings(self.path).get(self.sid)
        self.assertEqual(elapsed(reopened,620),60)
        row=self.live.transition(self.sid,row['version'],'finish',now=650)
        self.assertEqual(elapsed(row,999),90)
        self.assertEqual(row['status'],'ended')
    def test_notes_are_durable(self):
        self.live.save(self.sid,1,**self.fields())
        self.assertEqual(LiveMeetings(self.path).get(self.sid)['notes'],self.fields()['notes'])
    def test_stale_tab_cannot_overwrite_or_finish(self):
        self.live.save(self.sid,1,**self.fields(notes='Latest notes'))
        with self.assertRaisesRegex(ValueError,'another tab'):self.live.save(self.sid,1,**self.fields(notes='Old notes'))
        with self.assertRaises(ValueError):self.live.transition(self.sid,1,'finish',now=100)
        self.assertEqual(self.live.get(self.sid)['notes'],'Latest notes')
    def test_finished_notes_read_only(self):
        row=self.live.transition(self.sid,1,'finish',now=100)
        with self.assertRaises(ValueError):self.live.save(self.sid,row['version'],**self.fields())
        with self.assertRaises(ValueError):self.live.transition(self.sid,row['version'],'resume')
    def test_invalid_events_and_missing_sessions(self):
        for event in ('pause','resume','unknown'):
            with self.assertRaises(ValueError):self.live.transition(self.sid,1,event)
        with self.assertRaises(ValueError):self.live.get(999)
    def test_invalid_fields_do_not_mutate_saved_notes(self):
        for change in ({'title':''},{'notes':'x'*30001},{'call_url':'javascript:alert(1)'}):
            with self.assertRaises(ValueError):self.live.save(self.sid,1,**self.fields(**change))
        self.assertEqual(self.live.get(self.sid)['version'],1)
    def test_call_links_require_trusted_https_without_credentials(self):
        for url in ('https://meet.google.com/abc-defg-hij','https://example.zoom.us/j/123','https://teams.microsoft.com/l/meetup-join/example'):
            self.assertEqual(call_url(url),url)
        for url in ('http://meet.google.com/abc','https://meet.google.com.evil.test/a','https://user:secret@zoom.us/j/1','https://zoom.us:444/j/1','javascript:alert(1)'):
            with self.assertRaises(ValueError):call_url(url)
    def test_isolated_workspaces_and_export_preserve_notes(self):
        other=LiveMeetings(Path(self.temp.name)/'other.live.sqlite3');self.assertEqual(other.list(),[])
        row=self.live.save(self.sid,1,**self.fields())
        text=export_notes(row);self.assertIn(row['notes'],text);self.assertIn('Review launch',text);self.assertIn('Maya, Arjun',text)
    def test_clock_does_not_go_negative_after_clock_adjustment(self):
        row=self.live.transition(self.sid,1,'start',now=100)
        self.assertEqual(elapsed(row,50),0)

if __name__=='__main__':unittest.main()
