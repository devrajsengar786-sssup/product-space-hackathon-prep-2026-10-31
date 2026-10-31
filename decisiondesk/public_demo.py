"""Separate disposable visitor workspaces from the owner's local workspace."""
import os
from pathlib import Path
import uuid


def enabled():
    return os.environ.get('DECISIONDESK_PUBLIC_DEMO') == '1'


def session_database(state, root):
    if 'public_demo_id' not in state:
        state['public_demo_id'] = uuid.uuid4().hex
    identifier = state['public_demo_id']
    if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
        raise ValueError('Invalid demo session.')
    return Path(root) / identifier / 'decisiondesk.sqlite3'


def seed_fictional_workspace(store, reference_date):
    """Label scripted sample setup; it is not evidence of human approval or AI."""
    if store.list_meetings():
        return
    from .samples import get_demo_meetings
    from .analysis import analyze_transcript
    samples = get_demo_meetings(reference_date)
    for index, sample in enumerate(samples):
        result = analyze_transcript(sample['transcript'], sample['date'], engine='offline')
        mid = store.save_meeting('Fictional sample · ' + sample['title'], sample['transcript'], sample['date'], result)
        if index == 0:
            # Included sample setup only; no external task is created.
            actions = [action for action in result['actions'] if action.get('owner') and action.get('due_date')]
            store.approve_meeting(mid, actions, {})
