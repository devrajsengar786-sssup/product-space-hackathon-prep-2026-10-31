"""DecisionDesk: local meeting-to-execution workspace."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape
from pathlib import Path
import json
import hashlib
import os

import streamlit as st

from decisiondesk.analysis import AnalysisError, analyze_transcript, available_local_models
from decisiondesk.integrations import github_status, issue_body, publish_action
from decisiondesk.samples import get_demo_meetings
from decisiondesk.store import Store
from decisiondesk.features import calendar_export
from decisiondesk.workspaces import Workspaces
from decisiondesk.live import LiveMeetings, elapsed, export_notes, FIELDS
from decisiondesk.assistant import MODES, assist, workspace_sources, select_sources, fingerprint, clarify_tasks, export_answer

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('DECISIONDESK_DB_PATH', str(ROOT / 'data' / 'decisiondesk.sqlite3')))
TODAY = date.today()
DEFAULT_REPO = 'devrajsengar786-sssup/product-space-hackathon-prep-2026-10-31'
PAGES = ['Overview', 'AI Assistant', 'Live meeting', 'Capture meeting', 'Review & approve', 'Action board', 'Decision memory', 'Search memory', 'Timeline & changes', 'Weekly digest', 'Team insights', 'Workspace settings', 'Connections']

st.set_page_config(page_title='DecisionDesk · Meetings that move work', page_icon='◈', layout='wide')
st.markdown('<style>' + (ROOT / 'decisiondesk' / 'theme.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)

PREFERENCES_PATH = DB_PATH.parent / 'preferences.json'
try:
    preferences = json.loads(PREFERENCES_PATH.read_text(encoding='utf-8'))
except (OSError, ValueError):
    preferences = {}
if isinstance(preferences, dict) and preferences.get('engine') in ('offline', 'ollama'):
    st.session_state.setdefault('analysis_engine', preferences['engine'])
    if isinstance(preferences.get('model'), str):
        st.session_state.setdefault('ollama_model', preferences['model'])


def save_engine_preference(engine, model=''):
    PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES_PATH.write_text(json.dumps({'engine': engine, 'model': model}), encoding='utf-8')


catalog = Workspaces(DB_PATH)
workspace_options = catalog.list()
if 'switch_workspace' in st.session_state:
    st.session_state['workspace_picker'] = st.session_state.pop('switch_workspace')
active_workspace = st.session_state.get('workspace_picker', 'main')
if active_workspace not in {w['id'] for w in workspace_options}:
    active_workspace = 'main'
if st.session_state.get('active_workspace', 'main') != active_workspace:
    retained = {'workspace_picker','navigation','analysis_engine','ollama_model','local_models'}
    for state_key in list(st.session_state):
        if state_key not in retained:
            del st.session_state[state_key]
st.session_state['active_workspace'] = active_workspace
store = Store(catalog.path(active_workspace))
if 'jump_to' in st.session_state:
    st.session_state['navigation'] = st.session_state.pop('jump_to')


def jump(page: str):
    st.session_state['jump_to'] = page
    st.rerun()


def badge(text: str, gray=False):
    return f'<span class="tag {"tag-gray" if gray else ""}">{escape(str(text))}</span>'


def header(kicker, title, description):
    section = kicker.split('/')[-1].strip()
    st.markdown(f'<div class="desk-topbar"><div class="breadcrumb">DecisionDesk <span>/</span> <b>{escape(section)}</b></div><div class="desk-status"><i class="desk-dot"></i> LOCAL WORKSPACE</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="eyebrow">{escape(kicker)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="sub">{escape(description)}</div>', unsafe_allow_html=True)


def empty(title, body):
    st.markdown(f'<div class="empty">◇<strong>{escape(title)}</strong>{escape(body)}</div>', unsafe_allow_html=True)


def table_rows(rows, fields):
    return [{label: row.get(key) or '—' for label, key in fields} for row in rows]


def safe_due(raw):
    try:
        if raw is None or str(raw).strip() in ('', 'None', 'NaT', 'nan'):
            return ''
        return date.fromisoformat(str(raw)[:10]).isoformat()
    except ValueError:
        raise ValueError('Use a real deadline in YYYY-MM-DD format, or leave it blank.')


def meeting_picker():
    meetings = store.list_meetings()
    if not meetings:
        empty('Your first meeting starts here', 'Capture a meeting to turn the discussion into decisions and next steps.')
        if st.button('Capture a meeting', type='primary'):
            jump('Capture meeting')
        return None
    ids = [m['id'] for m in meetings]
    preferred = st.session_state.get('selected_meeting')
    selected = st.selectbox('Meeting', ids, index=ids.index(preferred) if preferred in ids else 0,
                            format_func=lambda mid: next(f"{m['title']} · {m['meeting_date']}" for m in meetings if m['id'] == mid))
    st.session_state['selected_meeting'] = selected
    return store.get_meeting(selected)


with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-icon">◈</span><div class="brand-word">DecisionDesk<small>MEETING INTELLIGENCE</small></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Your workspace</div>', unsafe_allow_html=True)
    st.selectbox('Project workspace', [w['id'] for w in workspace_options],
                 format_func=lambda wid: next(w['name'] for w in workspace_options if w['id']==wid), key='workspace_picker')
    page = st.radio('Workspace navigation', PAGES, key='navigation', label_visibility='collapsed', format_func=lambda name: {'Overview':'Dashboard','Connections':'AI & connections'}.get(name,name))
    st.divider()
    st.markdown(badge('LOCAL AI' if st.session_state.get('analysis_engine') == 'ollama' else 'RULES MODE', gray=True), unsafe_allow_html=True)
    st.caption('Local AI selected' if st.session_state.get('analysis_engine') == 'ollama' else 'No AI model connected. Rules mode is available for workflow testing.')
    st.markdown('<div class="sidebar-note"><strong>Every decision, accounted for.</strong><p>Your meeting memory stays on this computer. External tasks need your approval.</p></div><div class="sidebar-profile"><span class="profile-avatar">DD</span><div><strong>Your workspace</strong><small>Local access only</small></div></div>', unsafe_allow_html=True)

if st.session_state.pop('flash', None):
    st.success('Saved. Your workspace is up to date.')

if page == 'Overview':
    header('Workspace / Dashboard', 'Your work, at a glance.',
           'Review new meetings, see what needs attention, and keep the next steps moving.')
    meetings=store.list_meetings()
    actions=store.decorate_actions(store.list_actions())
    drafts=[m for m in meetings if m['status']=='draft']
    open_tasks=[a for a in actions if a['status'] in ('approved','published')]
    overdue=[a for a in open_tasks if a.get('due_date') and a['due_date']<TODAY.isoformat()]
    completed=[a for a in actions if a['status']=='done']
    metrics=[('Meetings to review',len(drafts),'◎'),('Open tasks',len(open_tasks),'▤'),('Overdue tasks',len(overdue),'◷'),('Completed tasks',len(completed),'✓')]
    cards=''.join(f'<div class="summary-card"><span class="summary-symbol">{symbol}</span><span>{label}</span><strong>{value}</strong></div>' for label,value,symbol in metrics)
    st.markdown('<div class="summary-grid">'+cards+'</div>',unsafe_allow_html=True)
    if st.button('Open live meeting workspace →'):jump('Live meeting')
    a,b,c=st.columns(3)
    if a.button('＋ Capture a meeting',type='primary',width='stretch'):jump('Capture meeting')
    if b.button('Ask your meetings',width='stretch'):
        st.session_state['assistant_mode']='Ask your meetings';jump('AI Assistant')
    if c.button('Prepare a meeting brief',width='stretch'):
        st.session_state['assistant_mode']='Meeting brief';jump('AI Assistant')
    left,right=st.columns([1.35,1])
    with left:
        st.subheader('Needs your attention')
        st.caption('Start here. Drafts do not change saved decisions or approved tasks.')
        if not drafts and not overdue and not any(a['blocked_by'] for a in open_tasks):
            empty('You’re up to date','No meetings await review and no approved tasks are overdue or blocked.')
        for m in drafts[:3]:
            with st.container(border=True):
                st.markdown(badge('Review needed'),unsafe_allow_html=True)
                st.write('**'+m['title']+'**')
                st.caption(f"{m['meeting_date']} · Check decisions, owners and deadlines")
                if st.button('Review meeting →',key=f"attention_{m['id']}"):
                    st.session_state['selected_meeting']=m['id'];jump('Review & approve')
        for a in overdue[:3]:
            st.markdown(f'<div class="attention-row"><b>{escape(a["title"])}</b><span>Overdue · {escape(a["owner"])} · {escape(a["due_date"])}</span></div>',unsafe_allow_html=True)
        blocked=sum(bool(a['blocked_by']) for a in open_tasks)
        if blocked:st.warning(f'{blocked} open task(s) are waiting on dependencies.')
        if overdue or blocked:
            if st.button('Manage tasks →'):jump('Action board')
        st.subheader('Recent meetings')
        if not meetings:
            empty('No meetings yet','Capture a conversation or load a fictional sample from Capture meeting.')
        for m in meetings[:4]:
            with st.container(border=True):
                st.write('**'+m['title']+'**')
                st.caption(m['meeting_date']+' · '+('Needs review' if m['status']=='draft' else 'Approved'))
                if st.button('Open meeting →',key=f"recent_{m['id']}"):
                    st.session_state['selected_meeting']=m['id'];jump('Review & approve')
    with right:
        st.subheader('Next deadlines')
        upcoming=sorted([a for a in open_tasks if a.get('due_date') and TODAY.isoformat()<=a['due_date']<=(TODAY+timedelta(days=7)).isoformat()],key=lambda a:a['due_date'])
        st.caption('Approved open work due today or in the next seven days.')
        if not upcoming:empty('No deadlines this week','Tasks appear here after you review and approve a meeting plan.')
        for a in upcoming[:5]:
            st.markdown(f'<div class="panel"><div class="card-title">{escape(a["title"])}</div><div class="card-meta">{escape(a["owner"])} · Due {escape(a["due_date"])}</div></div>',unsafe_allow_html=True)
        st.subheader('Current decisions')
        current=store.list_decisions()
        if not current:st.caption('Approved meeting decisions will appear here.')
        for d in current[:3]:
            with st.container(border=True):
                st.write('**'+d['topic'].title()+'**');st.write(d['statement'])
        if current and st.button('See decision history →'):jump('Timeline & changes')
        with st.expander('How DecisionDesk works'):
            st.write('1. Capture a conversation. 2. Review AI suggestions and fill missing details. 3. Approve locally. 4. Track the work or explicitly publish selected tasks.')
            st.caption('AI Assistant can answer questions and prepare drafts. It does not change your workspace or send messages.')

elif page == 'Live meeting':
    header('Workspace / Live meeting','Keep the conversation moving.',
           'Run an agenda, type or dictate notes with Wispr Flow, then turn the finished conversation into an AI-reviewed plan.')
    st.caption('This is a local meeting companion. It does not host calls, record audio, or automatically transcribe other participants. Use your usual meeting app for the call.')
    live=LiveMeetings(store.path.with_suffix('.live.sqlite3'))
    with st.expander('＋ New live meeting',expanded=not live.list()):
        with st.form('new_live_meeting'):
            new_title=st.text_input('New meeting title',max_chars=150,placeholder='e.g. Weekly product sync')
            new_day=st.date_input('Meeting day',value=TODAY)
            create_live=st.form_submit_button('Create live meeting',type='primary')
        if create_live:
            try:
                st.session_state['live_picker']=live.create(new_title,new_day.isoformat())
                st.rerun()
            except ValueError as error:st.error(str(error))
    sessions=live.list()
    if not sessions:
        empty('Your meeting space is ready','Create a session above. Notes stay in this project workspace and can be resumed later.')
    else:
        sid=st.selectbox('Live meeting session',[r['id'] for r in sessions],key='live_picker',format_func=lambda identifier:next(r['title']+' · '+r['status'] for r in sessions if r['id']==identifier))
        row=live.get(sid)
        prefix=f'live_{active_workspace}_{sid}_'
        version_key=prefix+'version'
        if version_key not in st.session_state:
            st.session_state[version_key]=row['version']
            for field in FIELDS:st.session_state[prefix+field]=row[field]
        def save_live_fields():
            try:
                updated=live.save(sid,st.session_state[version_key],**{field:st.session_state[prefix+field] for field in FIELDS})
                st.session_state[version_key]=updated['version']
                st.session_state.pop(prefix+'error',None)
            except ValueError as error:st.session_state[prefix+'error']=str(error)
        stale=row['version']!=st.session_state[version_key]
        if stale:st.warning('A newer version exists in another tab. Download your local notes before reloading to avoid losing edits.')
        if st.button('Reload saved session'):
            for key in list(st.session_state):
                if key.startswith(prefix):del st.session_state[key]
            st.rerun()
        @st.fragment(run_every=1 if row['status']=='running' else None)
        def meeting_clock():
            current=live.get(sid)
            seconds=int(elapsed(current));hours,rest=divmod(seconds,3600);minutes,seconds=divmod(rest,60)
            st.markdown(f'<div class="live-clock"><span>{escape(current["status"].upper())}</span><strong>{hours:02d}:{minutes:02d}:{seconds:02d}</strong><small>Meeting clock · paused time is excluded</small></div>',unsafe_allow_html=True)
        meeting_clock()
        controls=st.columns(3)
        events=[('start','Start meeting'),('pause','Pause meeting'),('resume','Resume meeting'),('finish','Finish meeting')]
        available={'ready':('start','finish'),'running':('pause','finish'),'paused':('resume','finish'),'ended':()}
        for index,(event,label) in enumerate(events):
            if event in available[row['status']] and controls[index%3].button(label,disabled=stale or bool(st.session_state.get(prefix+'error')),type='primary' if event in ('start','resume') else 'secondary'):
                try:
                    updated=live.transition(sid,st.session_state[version_key],event)
                    st.session_state[version_key]=updated['version'];st.rerun()
                except ValueError as error:st.error(str(error))
        locked=row['status']=='ended'
        left,right=st.columns([1,1.7])
        with left:
            st.text_input('Session title',key=prefix+'title',max_chars=150,on_change=save_live_fields,disabled=locked)
            st.text_input('Participants',key=prefix+'participants',max_chars=2000,on_change=save_live_fields,disabled=locked,placeholder='Names, separated by commas')
            st.text_input('Existing meeting link (optional)',key=prefix+'call_url',max_chars=2000,on_change=save_live_fields,disabled=locked,placeholder='Paste your Zoom, Meet or Teams HTTPS link')
            if row['call_url']:st.link_button('Open meeting call ↗',row['call_url'])
            st.text_area('Agenda',key=prefix+'agenda',height=220,max_chars=6000,on_change=save_live_fields,disabled=locked,placeholder='1. Review progress\n2. Make decisions\n3. Confirm next steps')
        with right:
            st.text_area('Live meeting notes',key=prefix+'notes',height=400,max_chars=30000,on_change=save_live_fields,disabled=locked,placeholder='Click here and dictate with Wispr Flow, or type.\nMaya: Decision: …\nArjun: I will … by …')
            st.caption('Notes save when the field is submitted or loses focus. Click Save notes now before closing the tab. Unsaved keystrokes can be lost if the browser closes.')
            if not locked and st.button('Save notes now',disabled=stale):
                save_live_fields();st.rerun()
            if st.session_state.get(prefix+'error'):st.error(st.session_state[prefix+'error'])
            elif not stale:st.caption('Saved locally · '+row['meeting_date']+' · No audio recording')
        local_copy=dict(row,**{field:st.session_state[prefix+field] for field in FIELDS})
        st.download_button('Download session notes',export_notes(local_copy),'decisiondesk-live-meeting.md','text/markdown')
        st.caption('Live sessions are stored separately from the workspace JSON backup. Download notes here; once analyzed and saved, the transcript is also included in the normal workspace backup.')
        if locked:
            st.success('Meeting finished. Its notes are preserved. Prepare AI review below; decisions and tasks still need your approval.')
        if st.button('Use finished notes for AI review →',type='primary',disabled=not locked or not row['notes'].strip() or stale):
            st.session_state['capture_title']=row['title']
            st.session_state['capture_date']=date.fromisoformat(row['meeting_date'])
            st.session_state['capture_text']=row['notes']
            jump('Capture meeting')
        if not locked:st.caption('Finish the meeting to prepare AI review. This does not approve or publish anything.')

elif page == 'AI Assistant':
    header('Workspace / AI Assistant','From meeting memory to a useful next step.',
           'Ask questions, prepare for meetings, and draft your follow-through with evidence from this workspace.')
    mode=st.selectbox('What would you like help with?',list(MODES),key='assistant_mode')
    descriptions={
        'Ask your meetings':'Ask what was decided, why something changed, or who committed to a task.',
        'Meeting brief':'Prepare an agenda from current decisions, open work and unanswered questions.',
        'Clarify missing details':'Find questions to resolve before you approve a meeting plan.',
        'Follow-up draft':'Draft a meeting update. Edit it and download it; nothing is sent automatically.',
        'Break down a task':'Suggest smaller steps and an order of work. Suggestions do not create tasks.',
        'Risk suggestions':'Review possible delivery concerns. These are suggestions, not predictions.'}
    st.info(descriptions[mode])
    all_sources=workspace_sources(store)
    meeting_id=None;task_id=None
    if mode=='Risk suggestions' and not any(source['id'].startswith('R') for source in all_sources):
        st.success('No overdue, incomplete, blocked, or conflicting-decision flags were found. This does not establish that delivery is risk-free.')
    if mode in ('Follow-up draft','Clarify missing details'):
        available_meetings=store.list_meetings()
        if available_meetings:
            meeting_id=st.selectbox('Source meeting',[m['id'] for m in available_meetings],format_func=lambda mid:next(m['title']+' · '+m['status'] for m in available_meetings if m['id']==mid),key='assistant_meeting')
    if mode=='Break down a task':
        available_tasks=[a for a in store.list_actions() if a['status'] in ('approved','published')]
        if available_tasks:
            task_id=st.selectbox('Task to break down',[a['id'] for a in available_tasks],format_func=lambda aid:next(a['title'] for a in available_tasks if a['id']==aid),key='assistant_task')
        else:st.warning('Approve an open task before asking for a breakdown.')
    if mode=='Clarify missing details' and meeting_id is not None:
        gaps=clarify_tasks(store.list_actions(meeting_id))
        if gaps:
            st.subheader('Missing details found')
            for gap in gaps:st.write('**'+gap['title']+'** — '+gap['question'])
            st.caption('These field checks do not use AI. Ask below for additional source-based questions, then enter confirmed answers in the meeting review.')
        if st.button('Open meeting review →'):
            st.session_state['selected_meeting']=meeting_id;jump('Review & approve')
    local_ready=st.session_state.get('analysis_engine')=='ollama' and bool(st.session_state.get('ollama_model'))
    if not local_ready:
        st.warning('Select a local AI model in AI & connections to generate assistance. No rules-based answer will be presented as AI.')
        if st.button('Set up local AI →'):jump('Connections')
    with st.form('assistant_request'):
        query=st.text_area('Your question' if mode=='Ask your meetings' else 'Focus or extra instructions (optional)',max_chars=2000,key='assistant_query_'+mode,placeholder='e.g. Why did the launch date change?' if mode=='Ask your meetings' else 'e.g. Focus on launch readiness and unanswered questions')
        generate=st.form_submit_button({'Ask your meetings':'Ask AI','Meeting brief':'Prepare brief','Clarify missing details':'Suggest clarification questions','Follow-up draft':'Draft follow-up','Break down a task':'Suggest task steps','Risk suggestions':'Review possible risks'}[mode],type='primary',disabled=not local_ready or not all_sources or (mode=='Break down a task' and task_id is None) or (mode=='Risk suggestions' and not any(source['id'].startswith('R') for source in all_sources)))
    sources=select_sources(all_sources,query,mode,meeting_id,task_id)
    scope=fingerprint(sources)+mode+query+str(meeting_id)+str(task_id)+st.session_state.get('ollama_model','')
    result_key=hashlib.sha256(scope.encode()).hexdigest()
    if generate:
        st.session_state.pop('assistant_result',None)
        if mode=='Ask your meetings' and len(query.strip())<3:st.error('Enter a question first.')
        else:
            try:
                with st.spinner('Reading selected sources with local AI… This may take a minute.'):
                    result=assist(mode,query or descriptions[mode],sources,model=st.session_state['ollama_model'],as_of=TODAY.isoformat())
                st.session_state['assistant_result']={'key':result_key,'result':result}
            except AnalysisError as error:st.error(str(error))
    if not all_sources:empty('Start with a conversation','Capture a meeting first. The assistant uses only sources in the selected project workspace.')
    if sources:
        with st.expander(f'Sources available for this request · {len(sources)} selected excerpts'):
            st.caption('This is a bounded selection, not a search of every word. Try a specific topic or name if an answer is missing.')
            for source in sources:
                st.caption(source['id']+' · '+source['title']+' · '+source['status']);st.text(source['text'])
    saved=st.session_state.get('assistant_result',{})
    if saved.get('key')==result_key:
        result=saved['result']
        st.subheader('AI draft · review before using')
        st.caption('Quotes are checked against selected sources. AI interpretations and proposed steps can still be wrong. Nothing has been approved, created or sent.')
        if result['omitted']:st.warning(f"{result['omitted']} unsupported item(s) were omitted because their citations could not be verified.")
        if not result['items']:st.info('No supported answer was returned. Try a more specific question or another source meeting.')
        for index,item in enumerate(result['items']):
            with st.container(border=True):
                st.write(item['text'])
                st.caption(item['source_id']+' · '+item['source']['title']+' · '+item['source']['status'])
                st.text('“'+item['quote']+'”')
                if st.button('Open source meeting →',key=f'assistant_source_{result_key}_{index}'):
                    st.session_state['selected_meeting']=item['source']['meeting_id'];jump('Review & approve')
        if result['unanswered']:st.warning('Still unclear: '+result['unanswered'])
        if result['items']:
            st.text_area('Edit your draft',value=export_answer(result),height=260,key='assistant_edit_'+result_key)
            st.download_button('Download edited draft',st.session_state['assistant_edit_'+result_key],'decisiondesk-'+mode.lower().replace(' ','-')+'.md','text/markdown')

elif page == 'Capture meeting':
    header('Workspace / Capture', 'Start with the conversation.',
           'Dictate with Wispr Flow into the meeting field, type, or paste a speaker-labelled transcript. Your input stays local in this workspace.')
    st.markdown('<div class="step"><b>01 Capture</b>　→　02 Review decisions　→　03 Approve actions　→　04 Follow through</div>', unsafe_allow_html=True)
    left, right = st.columns([2.2, 1])
    samples = get_demo_meetings(TODAY.isoformat())
    with right:
        uploaded = st.file_uploader('Import a text transcript', type=['txt'], help='UTF-8 text, up to 30,000 characters. It stays in this local workspace.')
        if uploaded is not None and st.button('Use uploaded transcript', width='stretch'):
            try:
                if uploaded.size > 120000:
                    raise ValueError('Use a smaller text file: up to 30,000 characters.')
                uploaded_text = uploaded.getvalue().decode('utf-8-sig')
                if len(uploaded_text) > 30000:
                    raise ValueError('Use a transcript with no more than 30,000 characters.')
                st.session_state['capture_text'] = uploaded_text
                st.session_state['capture_title'] = Path(uploaded.name).stem[:150]
                st.rerun()
            except (UnicodeError, ValueError):
                st.error('Use a UTF-8 .txt file containing no more than 30,000 characters.')
        st.subheader('A quick start')
        st.write('Use the fictional Atlas meetings to explore the full workflow.')
        for index, label in enumerate(['Load planning meeting', 'Load follow-up meeting']):
            if st.button(label, width='stretch'):
                sample = samples[index]
                st.session_state['capture_title'] = sample['title']
                st.session_state['capture_date'] = date.fromisoformat(sample['date'])
                st.session_state['capture_text'] = sample['transcript']
                st.rerun()
        st.markdown('<div class="panel"><div class="card-title">Make room for real speech</div><div class="card-body">Click the meeting field, then use your Wispr Flow shortcut. Include speaker names when the speaker changes. You can say corrections naturally.</div><div class="small">Typing remains available as an accessibility option. Organizer approval for typing-only participation is still unconfirmed.</div></div>', unsafe_allow_html=True)
        engine = st.session_state.get('analysis_engine', 'offline')
        st.caption('Analysis: local Ollama model. No cloud requests.' if engine == 'ollama' else 'Analysis: offline rules. This is not a live AI model.')
        if st.button('Manage connections'):
            jump('Connections')
    with left:
        if st.session_state.pop('sample_choice', None):
            st.session_state['capture_title'] = samples[0]['title']
            st.session_state['capture_date'] = date.fromisoformat(samples[0]['date'])
            st.session_state['capture_text'] = samples[0]['transcript']
        with st.form('capture_meeting'):
            title = st.text_input('Meeting title', placeholder='e.g. Atlas · Launch planning', key='capture_title', max_chars=150)
            meeting_day = st.date_input('Meeting date', key='capture_date')
            transcript = st.text_area('Meeting conversation', height=340, placeholder='Maya: Decision: launch date is 2026-11-06.\nArjun: I will prepare the demo by tomorrow.', key='capture_text', max_chars=30000)
            st.caption('Speaker labels help attribute ownership. Review every suggestion before accepting it.')
            analyze = st.form_submit_button('Find decisions & actions →', type='primary', width='stretch')
        if analyze:
            if not title.strip() or not transcript.strip():
                st.error('Add a title and a meeting conversation first.')
            else:
                try:
                    with st.spinner('Reading the discussion and checking decision memory…'):
                        analysis = analyze_transcript(transcript, meeting_day.isoformat(),
                            engine=st.session_state.get('analysis_engine', 'offline'),
                            model=st.session_state.get('ollama_model', ''))
                        meeting_id = store.save_meeting(title.strip(), transcript, meeting_day.isoformat(), analysis)
                    st.session_state['selected_meeting'] = meeting_id
                    jump('Review & approve')
                except (AnalysisError, ValueError) as error:
                    st.error(str(error))
                except Exception:
                    st.error('The meeting could not be processed. Your input is still here; check the connection and try again.')

elif page == 'Review & approve':
    header('Workspace / Review', 'A clear plan. Your final say.',
           'Check the evidence, resolve changed decisions, and edit the proposed actions before they enter your workspace.')
    meeting = meeting_picker()
    if meeting:
        mid = meeting['id']
        analysis = meeting['analysis']
        st.markdown(badge(str(meeting.get('status', 'draft')).title()) + badge(analysis.get('engine', 'offline'), True), unsafe_allow_html=True)
        st.subheader(meeting['title'])
        st.write(analysis.get('summary', ''))
        if analysis.get('warnings'):
            with st.expander(f"{len(analysis['warnings'])} item(s) need attention", expanded=True):
                for warning in analysis['warnings']:
                    st.write('• ' + str(warning))
        with st.expander('Source conversation & speakers'):
            st.caption('Speakers: ' + ', '.join(analysis.get('speakers', [])))
            st.text(meeting['transcript'])
        if meeting.get('status') != 'draft':
            st.success('This meeting has been approved. Its accepted decisions are in memory; tasks are ready in the action board.')
            if st.button('Open action board →', type='primary'):
                jump('Action board')
        else:
            decisions = analysis.get('decisions', [])
            memory_version = store.memory_version()
            conflicts = store.find_conflicts(decisions)
            st.subheader('Decision check')
            resolutions = {}
            selected_decisions = []
            if not decisions:
                st.info('No clear decision was found. Actions can still be reviewed below.')
            for i, decision in enumerate(decisions):
                matches = [c for c in conflicts if c['proposed_index'] == i]
                with st.container(border=True):
                    include_decision = st.checkbox('Keep this decision in the accepted plan', value=True, key=f'keep_decision_{mid}_{i}')
                    if include_decision:
                        selected_decisions.append(i)
                    st.markdown(f"**{decision.get('topic', 'Decision').replace('_',' ').title()}**")
                    st.write(decision.get('statement', ''))
                    if decision.get('evidence'):
                        st.caption('Source: ' + decision['evidence'])
                    if matches and include_decision:
                        st.warning('This differs from an accepted decision.')
                        for conflict in matches:
                            st.write('**Earlier:** ' + conflict['previous_statement'])
                            st.caption(conflict.get('reason', 'Review the changed value.'))
                        choice = st.radio('Which decision should the workspace keep?',
                            ['Choose a resolution', 'Keep the earlier decision', 'Accept this meeting’s update'],
                            key=f'resolution_{mid}_{memory_version}_{i}')
                        if choice != 'Choose a resolution':
                            resolutions[str(i)] = 'keep_previous' if choice == 'Keep the earlier decision' else 'replace'
                    elif include_decision:
                        st.caption('No changed value found in accepted decision memory.')
                    else:
                        st.caption('Excluded. This suggestion will not update decision memory.')
            st.subheader('Proposed actions')
            actions = analysis.get('actions', [])
            if actions:
                editable = [{'Include': bool(a.get('owner')) and str(a.get('owner')).casefold() not in ('unassigned', 'unknown') and bool(a.get('due_date')), 'Title': a.get('title',''), 'Owner': a.get('owner',''),
                            'Due': a.get('due_date',''), 'Description': a.get('description',''),
                            'Evidence': a.get('evidence','')} for a in actions]
                st.caption('Suggestions missing an owner or deadline start excluded. Fill in the missing details and check Keep to include them.')
                edited = st.data_editor(editable, hide_index=True, width='stretch',
                    disabled=['Evidence'], key=f'action_editor_{mid}',
                    column_config={'Include':st.column_config.CheckboxColumn('Keep', width='small'),
                        'Due':st.column_config.TextColumn('Deadline (YYYY-MM-DD)'),
                        'Evidence':st.column_config.TextColumn('Source evidence', width='large')})
            else:
                edited = []
                st.info('No explicit action was found. You can still save this meeting’s accepted decisions.')
            approve = st.checkbox('I reviewed the decisions and proposed actions. Save the accepted plan locally.', key=f'approve_{mid}')
            if st.button('Approve & save plan', type='primary', disabled=not approve):
                try:
                    clean = [{'title':str(r.get('Title') or '').strip(), 'owner':str(r['Owner'] or '').strip(),
                              'due_date':safe_due(r['Due']), 'description':str(r['Description'] or ''),
                              'evidence':r['Evidence']} for r in edited if r['Include']]
                    if any(not row['title'] for row in clean):
                        raise ValueError('Every included action needs a title.')
                    if any(row['owner'].casefold() in ('', 'unassigned', 'unknown') or not row['due_date'] for row in clean):
                        raise ValueError('Give each included action an owner and deadline, or uncheck Keep to exclude it.')
                    store.approve_meeting(mid, clean, resolutions, decision_indices=selected_decisions, expected_memory_version=memory_version)
                    st.session_state['flash'] = True
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

elif page == 'Action board':
    header('Workspace / Actions', 'The follow-through lives here.',
           'Track approved next steps, see what is due, and send tasks to GitHub only when you explicitly confirm.')
    actions = store.decorate_actions(store.list_actions())
    cols = st.columns([1, 1, 2])
    owners = sorted({a.get('owner') or 'Unassigned' for a in actions})
    owner_filter = cols[0].selectbox('Owner', ['Everyone'] + owners)
    state_filter = cols[1].selectbox('Status', ['All', 'approved', 'published', 'done', 'draft'])
    if not actions:
        empty('No loose ends yet', 'Capture and approve a meeting to start tracking its actions.')
    shown = [a for a in actions if (owner_filter == 'Everyone' or (a.get('owner') or 'Unassigned') == owner_filter)
             and (state_filter == 'All' or a['status'] == state_filter)]
    st.caption(f'{len(shown)} of {len(actions)} tasks · Filters affect the board below.')
    if actions and not shown:
        empty('No matching tasks', 'Try Everyone and All to clear the filters.')
    for action in shown:
        with st.container(border=True):
            ca, cb = st.columns([5, 1])
            with ca:
                st.markdown(f"**{action['title']}**")
                st.markdown(badge(action['status'].title(), True) + badge(action.get('priority','Normal')) + (badge('Blocked', True) if action['blocked_by'] else ''), unsafe_allow_html=True)
                st.caption(f"{action.get('owner') or 'Unassigned'} · Due {action.get('due_date') or 'Not set'}")
                if action.get('description'):
                    st.write(action['description'])
                if action.get('external_url'):
                    st.link_button('Open GitHub issue ↗', action['external_url'])
            with cb:
                if action['status'] in ('approved','published') and st.button('Mark done', key=f"done_{action['id']}", disabled=bool(action['blocked_by'])):
                    store.update_action_status(action['id'], 'done')
                    st.rerun()
                if action['status']=='done' and st.button('Reopen',key=f"reopen_{action['id']}"):
                    store.update_action_status(action['id'],'approved')
                    st.rerun()
            if action['blocked_by']:
                st.caption('Waiting on: '+', '.join(a['title'] for a in action['blocked_by']))
            if action['status']!='draft':
                with st.expander('Edit task details & dependencies'):
                    with st.form(f"edit_task_{action['id']}"):
                        edit_title=st.text_input('Task title',value=action['title'])
                        edit_owner=st.text_input('Task owner',value=action['owner'])
                        edit_due=st.date_input('Deadline',value=date.fromisoformat(action['due_date']) if action.get('due_date') else TODAY)
                        edit_priority=st.selectbox('Priority',['Low','Normal','High','Urgent'],index=['Low','Normal','High','Urgent'].index(action.get('priority','Normal')))
                        edit_description=st.text_area('Task description',value=action.get('description',''))
                        dependency_options=[a['id'] for a in actions if a['id']!=action['id'] and a['status']!='draft']
                        edit_dependencies=st.multiselect('Must finish first',dependency_options,default=action['dependencies'],format_func=lambda aid: next(a['title'] for a in actions if a['id']==aid))
                        st.caption('Edits stay local. Already-created GitHub Issues are not automatically updated.')
                        save_edit=st.form_submit_button('Save task changes')
                    if save_edit:
                        try:
                            store.edit_action(action['id'],title=edit_title,owner=edit_owner,due_date=edit_due.isoformat(),description=edit_description,priority=edit_priority,dependencies=edit_dependencies)
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))
            if action['status'] == 'draft':
                st.caption('Awaiting meeting review. Draft tasks cannot be posted.')
    due = store.due_actions(TODAY.isoformat(), days=7)
    st.download_button('Export open deadlines to calendar',calendar_export(actions),'decisiondesk-deadlines.ics','text/calendar',help='All-day due dates. Import the file into your calendar; it does not send invitations.')
    with st.expander(f'Upcoming reminders · {len(due)} actions', expanded=bool(due)):
        st.caption('Workspace-wide reminders, independent of the board filters. Due-soon and overdue items are shown here while the app is open. No background messages or email notifications are sent.')
        if due:
            st.dataframe(table_rows(due, [('Action','title'),('Owner','owner'),('Deadline','due_date'),('Status','status')]), hide_index=True, width='stretch')
        else:
            st.write('No open tasks with a deadline in the next seven days.')
    st.divider()
    st.subheader('Publish approved tasks to GitHub')
    st.caption('Workspace-wide approval queue, independent of the board filters above.')
    approved = [a for a in actions if a['status'] == 'approved']
    if not approved:
        st.caption('Approve actions in a meeting review before publishing. Previously published actions are never posted again automatically.')
    else:
        repo = st.text_input('Destination repository (owner/name)', value=st.session_state.get('github_repo', DEFAULT_REPO))
        chosen = st.multiselect('Tasks to publish', [a['id'] for a in approved],
            format_func=lambda aid: next(a['title'] for a in approved if a['id']==aid))
        selected_actions = [a for a in approved if a['id'] in chosen]
        for selected_action in selected_actions:
            with st.expander('Issue preview: ' + selected_action['title'], expanded=True):
                st.caption('Destination: ' + repo)
                st.text('Title: ' + selected_action['title'])
                st.text(issue_body(selected_action))
        st.caption('This creates real GitHub Issues using the signed-in GitHub CLI. Task titles, descriptions, owners, deadlines and meeting evidence will leave this computer.')
        consent_scope = hashlib.sha256(json.dumps({'repo':repo, 'actions':selected_actions}, sort_keys=True, default=str).encode()).hexdigest()[:16]
        confirmed = st.checkbox(f'I approve creating {len(chosen)} issue(s) in {repo}.', key='github_post_consent_' + consent_scope)
        if st.button('Create selected GitHub Issues', type='primary', disabled=not (confirmed and chosen)):
            results = []
            for aid in chosen:
                try:
                    url = publish_action(store, aid, repo.strip(), confirmed=True)
                    results.append(url)
                except (ValueError, RuntimeError) as error:
                    st.error(str(error))
                    break
            if results:
                st.success(f'Created {len(results)} issue(s).')
                for url in results:
                    st.link_button('Open created issue ↗', url)
                st.session_state['github_repo'] = repo.strip()
                st.caption('Refresh the action board to see updated publication status.')

elif page == 'Decision memory':
    header('Workspace / Memory', 'Keep the context. Catch the change.',
           'Only reviewed and accepted decisions enter memory. New meetings are checked against these commitments.')
    decisions = store.list_decisions()
    if not decisions:
        empty('A memory worth building', 'Approve the planning sample, then analyze the follow-up to see a changed launch decision flagged.')
    for decision in decisions:
        st.markdown(f'<div class="panel"><div class="card-top"><div class="card-title">{escape(str(decision.get("topic", "Decision")).replace("_"," ").title())}</div>{badge("Accepted", True)}</div><div class="card-body">{escape(decision.get("statement", ""))}</div><div class="card-meta">{escape(decision.get("owner") or "Team decision")} · {escape(str(decision.get("meeting_date") or decision.get("updated_at") or ""))}</div></div>', unsafe_allow_html=True)
    if decisions:
        st.download_button('Download decision memory', json.dumps(decisions, indent=2, default=str), 'decisiondesk-memory.json', 'application/json')

elif page == 'Weekly digest':
    header('Workspace / Digest', 'One person. One clear picture.',
           'Bring accepted decisions, assigned actions, and upcoming deadlines into a concise weekly update.')
    as_of = st.date_input('Week ending', value=TODAY)
    all_actions = store.list_actions()
    people = sorted({a.get('owner') for a in all_actions if a.get('owner')})
    owner = st.selectbox('Digest for', ['Everyone'] + people)
    digest = store.weekly_digest(as_of.isoformat(), owner=None if owner=='Everyone' else owner)
    lines = [f'# DecisionDesk weekly digest — {as_of.isoformat()}', '', '## Team decision context (current accepted memory)']
    decisions = store.list_decisions()
    for d in decisions:
        lines.append('- ' + d.get('statement',''))
    if not decisions:
        lines.append('- No accepted decisions yet.')
    if not digest:
        empty('Your digest is waiting for the work', 'Approve some meeting actions to generate a person-by-person summary.')
    for person, buckets in digest.items():
        st.subheader(person)
        lines += ['', f'## {person}']
        for label, bucket in [('Overdue', 'overdue'), ('Due in the next 7 days', 'due_soon'), ('Completed this week', 'completed'), ('All open actions', 'open')]:
            items = buckets.get(bucket, [])
            if not items:
                continue
            st.caption(label.upper())
            lines += ['', f'### {label}']
            for a in items:
                text = f"{a['title']} — due {a.get('due_date') or 'not set'} · {a['status']}"
                st.write('☑ ' + text if a['status']=='done' else '○ ' + text)
                lines.append('- ' + text + (f" ({a['external_url']})" if a.get('external_url') else ''))
    st.caption('Groups open actions, approaching deadlines, overdue work, and completions in the selected week. Team decision context is current memory, not a historical snapshot. Export is local; nothing is sent to other people.')
    st.download_button('Download weekly digest', '\n'.join(lines), f'decisiondesk-digest-{as_of}.md', 'text/markdown')

elif page == 'Search memory':
    header('Workspace / Search','Find the conversation behind the commitment.',
           'Search only this workspace. Every result links back to its source meeting.')
    query=st.text_input('Search meetings, decisions and tasks',placeholder='Try launch, release notes, or a person’s name')
    kind=st.selectbox('Search in',['All','Meetings','Decisions','Tasks'])
    results=store.search(query,kind)
    if len(query.strip())<2:
        empty('A source for every answer','Enter at least two characters to search meeting text, decision evidence, and task descriptions.')
    elif not results:
        empty('No results in this workspace','Try a shorter phrase or switch the record type to All.')
    else:
        st.caption(f'{len(results)} results · up to 200 shown')
        for result in results:
            with st.container(border=True):
                st.markdown(badge(result['kind'])+badge(result['status'],True),unsafe_allow_html=True)
                st.write('**'+result['title']+'**')
                st.text(result['snippet'])
                if st.button('Open source meeting →',key=f"search_{result['kind']}_{result['id']}"):
                    st.session_state['selected_meeting']=result['meeting_id']
                    jump('Review & approve')

elif page == 'Timeline & changes':
    header('Workspace / Timeline','A decision has a history.',
           'See accepted changes and their meeting sources. Draft suggestions stay separate from accepted history.')
    timeline_tab,changes_tab=st.tabs(['Decision timeline','Since the last meeting'])
    with timeline_tab:
        history=store.decision_timeline()
        topic=st.selectbox('Decision topic',['All topics']+sorted({d['topic'] for d in history}))
        if not history:
            empty('Your history starts with approval','Accept a meeting decision to start its timeline. Replaced values remain visible here.')
        for d in history:
            if topic!='All topics' and d['topic']!=topic:
                continue
            with st.container(border=True):
                st.markdown(badge('Current' if d['active'] else 'Superseded',not d['active']),unsafe_allow_html=True)
                st.write('**'+d['topic'].title()+'**')
                st.write(d['statement'])
                if d['previous_value'] is not None:
                    st.caption(f"Changed from {d['previous_value']} → {d['value']}")
                st.caption(f"{d['meeting_title']} · Meeting {d['meeting_date']} · Accepted locally {d['created_at']}")
                with st.expander('Supporting source'):
                    st.text(d.get('evidence') or 'No source excerpt stored.')
                if st.button('Open source meeting →',key=f"timeline_{d['id']}"):
                    st.session_state['selected_meeting']=d['meeting_id'];jump('Review & approve')
    with changes_tab:
        changes=store.changes_since_last_meeting()
        meeting=changes['meeting']
        if not meeting:
            empty('Compare your next conversation','Capture a meeting to see new commitments, completed work, and changed decisions.')
        else:
            st.subheader(meeting['title'])
            st.caption(f"Most recent meeting by date · {meeting['meeting_date']} · {meeting['status']}")
            if meeting['status']=='draft':
                st.info('This meeting is awaiting review. The following are suggestions, not accepted changes.')
                for conflict in store.find_conflicts(meeting['analysis'].get('decisions',[])):
                    st.warning(conflict['previous_statement']+' → '+conflict['proposed_statement'])
            else:
                for d in changes['decisions']:
                    st.write(f"**{d['topic'].title()}:** {d['previous_value'] or 'New decision'} → {d['value']}")
            st.write(f"**{len(changes['actions'])} meeting tasks · {len(changes['completed'])} completions since capture**")
            for a in changes['actions']:
                st.write(f"• {a['title']} — {a['owner']} · {a['status']}")
            due=store.due_actions(TODAY.isoformat())
            st.caption(f'{len(due)} workspace tasks are overdue or approaching their deadlines.')
            if st.button('Review this meeting',type='primary'):
                st.session_state['selected_meeting']=meeting['id'];jump('Review & approve')

elif page == 'Team insights':
    header('Workspace / Insights','A clearer picture of the work.',
           'Measured from approved tasks in this workspace. Drafts are excluded; no estimated productivity claims.')
    analytics=store.analytics(TODAY.isoformat())
    a,b,c=st.columns(3)
    a.metric('Approved tasks',analytics['total']);b.metric('Completed',analytics['completed']);c.metric('Blocked',analytics['blocked'])
    st.progress(analytics['completion_rate']/100,text=f"{analytics['completion_rate']}% of approved tasks completed")
    if analytics['people']:
        st.subheader('Workload by owner')
        st.bar_chart(analytics['people'],x='Owner',y=['Open','Completed'])
        st.dataframe(analytics['people'],hide_index=True,width='stretch')
    else:
        empty('Insights grow with your work','Approve a meeting plan to see actual workload, completion, and overdue counts.')

elif page == 'Workspace settings':
    header('Workspace / Settings','A place for every project.',
           'Separate meeting memory, tasks, and backups by workspace. All data remains on this computer.')
    st.subheader('Create a workspace')
    with st.form('create_workspace'):
        workspace_name=st.text_input('Workspace name',max_chars=80,placeholder='e.g. Product launch')
        create_workspace=st.form_submit_button('Create workspace',type='primary')
    if create_workspace:
        try:
            new_id=catalog.create(workspace_name)
            st.session_state['switch_workspace']=new_id
            st.rerun()
        except ValueError as error:
            st.error(str(error))
    st.divider()
    st.subheader('Backup this workspace')
    st.caption('Live meeting sessions have a separate Download session notes button in Live meeting. They are not included in this JSON backup.')
    st.caption('The JSON backup contains meeting transcripts and local task history. Store it privately. Credentials are not included.')
    workspace_label=next(w['name'] for w in workspace_options if w['id']==active_workspace)
    st.download_button('Download workspace backup',store.export_backup(),f'decisiondesk-backup-{TODAY}.json','application/json')
    st.subheader('Restore into this workspace')
    st.caption('Restore is available only for an empty workspace. Create a new one above to preserve existing work. Imported published issues retain their URLs and will not be posted again automatically.')
    backup=st.file_uploader('DecisionDesk backup (.json)',type=['json'],key='backup_file')
    if backup is not None:
        if backup.size>20_000_000:
            st.error('Use a backup smaller than 20 MB.')
        else:
            backup_bytes=backup.getvalue()
            scope=hashlib.sha256(backup_bytes).hexdigest()[:16]
            restore_consent=st.checkbox(f'Restore this backup into {workspace_label}.',key=f'restore_{active_workspace}_{scope}')
            if st.button('Validate & restore',disabled=not restore_consent):
                try:
                    store.restore_backup(backup_bytes.decode('utf-8-sig'))
                    st.success('Workspace restored. Open Overview to review the imported records.')
                except (ValueError,UnicodeError) as error:
                    st.error(str(error))

elif page == 'Connections':
    header('Workspace / Connections', 'A small stack. Clear boundaries.',
           'Keep the workflow local. Connect a local AI model when available and publish only the tasks you approve.')
    ai, tracker = st.columns(2)
    with ai:
        with st.container(border=True):
            st.subheader('Analysis engine')
            mode = st.selectbox('Mode', ['Offline rules', 'Local AI · Ollama'], index=1 if st.session_state.get('analysis_engine')=='ollama' else 0)
            if mode == 'Offline rules':
                st.session_state['analysis_engine'] = 'offline'
                save_engine_preference('offline')
                st.info('Works without an account. Explicitly rule-based: limited language coverage and no live AI model. Use it to test the workflow, not as evidence of AI integration.')
            else:
                st.caption('Uses only Ollama on this computer at 127.0.0.1:11434. A model must already be installed. This app does not install software or download models.')
                if st.button('Check local models'):
                    with st.spinner('Checking this computer…'):
                        st.session_state['local_models'] = available_local_models()
                models = st.session_state.get('local_models', [])
                if models:
                    preferred_model = st.session_state.get('ollama_model')
                    model = st.selectbox('Installed model', models, index=models.index(preferred_model) if preferred_model in models else 0)
                    if st.button('Use this local model', type='primary'):
                        st.session_state['ollama_model'] = model
                        st.session_state['analysis_engine'] = 'ollama'
                        save_engine_preference('ollama', model)
                        st.success('Local model selected. The next analysis will use it; connection success is verified only by a completed analysis.')
                elif st.session_state.get('ollama_model') and 'local_models' not in st.session_state:
                    st.info('Saved model: '+st.session_state['ollama_model']+'. Check local models to refresh availability.')
                else:
                    st.warning('No local model detected yet. Offline rules remain available. No paid provider is configured.')
            st.caption('No API key fields, cloud billing, or automatic fallback to a different provider.')
    with tracker:
        with st.container(border=True):
            st.subheader('GitHub Issues')
            st.write('Approved actions can become real issues through your existing GitHub sign-in.')
            st.code(st.session_state.get('github_repo', DEFAULT_REPO), language=None)
            if st.button('Check GitHub connection'):
                with st.spinner('Checking existing sign-in…'):
                    result = github_status()
                (st.success if result.get('available') else st.warning)(result.get('message','Connection check complete.'))
            st.caption('Checking is read-only. Actual posting requires selecting tasks and confirming their repository in the action board.')
        with st.container(border=True):
            st.subheader('Wispr Flow')
            st.write('Click the meeting input and use your Wispr shortcut to dictate. Flow types into the focused field; no separate Flow API is used.')
            st.caption('Keyboard fallback is available. It does not by itself verify the hackathon’s mandatory voice-use requirement. Organizer accommodation remains unconfirmed.')
    st.divider()
    st.subheader('Workspace data')
    st.write('Meeting transcripts and approved work are stored in a local SQLite database. The data folder is excluded from Git.')
    st.caption('Use fictional or non-sensitive meetings for the demo. No automatic emails, recordings, or background reminders are enabled.')
