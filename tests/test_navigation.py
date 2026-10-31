import unittest
from decisiondesk.navigation import SECTIONS,VIEW_KEYS,destination,apply_destination,route_for

class NavigationTests(unittest.TestCase):
    def test_every_existing_workflow_has_a_roundtrip_destination(self):
        self.assertEqual(list(SECTIONS),['Dashboard','New meeting','Meeting memory','Tasks','AI Assistant','Reports','Settings'])
        expected={'Overview','Capture meeting','Live meeting','Review & approve','Action board','AI Assistant','Search memory','Decision memory','Timeline & changes','Weekly digest','Team insights','Workspace settings','Connections'}
        actual={page for views in SECTIONS.values() for page in views.values()}
        self.assertEqual(expected,actual)
        for page in actual:
            section,view=destination(page)
            self.assertEqual(route_for(section,view),page)
    def test_legacy_navigation_migration_preserves_unrelated_work(self):
        state={'capture_text':'Unsaved meeting notes','selected_meeting':9}
        apply_destination(state,'Review & approve')
        self.assertEqual(state['navigation'],'Meeting memory')
        self.assertEqual(state['memory_view'],'Review meetings')
        self.assertEqual(state['capture_text'],'Unsaved meeting notes')
        self.assertEqual(state['selected_meeting'],9)
        apply_destination(state,'Live meeting')
        self.assertEqual(state['new_meeting_view'],'Live notes')
    def test_section_defaults_and_invalid_destination(self):
        for section in SECTIONS:
            state={};apply_destination(state,section)
            self.assertEqual(state['navigation'],section)
            self.assertIn(route_for(section,'stale view'),SECTIONS[section].values())
        with self.assertRaises(ValueError):destination('Unknown route')

if __name__=='__main__':unittest.main()
