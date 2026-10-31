"""Seven main sections with explicit destinations for existing workflows."""
SECTIONS = {
    'Dashboard': {'Overview': 'Overview'},
    'New meeting': {'Paste transcript': 'Capture meeting', 'Live notes': 'Live meeting'},
    'Meeting memory': {'Search': 'Search memory', 'Decisions': 'Decision memory', 'History': 'Timeline & changes', 'Review meetings': 'Review & approve'},
    'Tasks': {'Tasks': 'Action board'},
    'AI Assistant': {'AI Assistant': 'AI Assistant'},
    'Reports': {'Weekly digest': 'Weekly digest', 'Team insights': 'Team insights'},
    'Settings': {'Workspace': 'Workspace settings', 'Connections': 'Connections'},
}
VIEW_KEYS = {'New meeting':'new_meeting_view','Meeting memory':'memory_view','Reports':'reports_view','Settings':'settings_view'}


def destination(route):
    for section, views in SECTIONS.items():
        for view,page in views.items():
            if page==route:return section,view
    if route in SECTIONS:return route,next(iter(SECTIONS[route]))
    raise ValueError('Unknown navigation destination.')


def apply_destination(state,route):
    section,view=destination(route)
    state['navigation']=section
    if section in VIEW_KEYS:state[VIEW_KEYS[section]]=view


def route_for(section,view=None):
    views=SECTIONS[section]
    return views.get(view,next(iter(views.values())))
