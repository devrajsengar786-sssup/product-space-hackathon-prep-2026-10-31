from datetime import date
import json
from pathlib import Path
import tempfile
import time
from decisiondesk.store import Store
from decisiondesk.assistant import MODES,assist,workspace_sources,select_sources

report=[]
Path('data').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='decisiondesk-assistant-live-') as temp:
    store=Store(Path(temp)/'workspace.sqlite3')
    transcript='Maya: Decision: launch date is 2026-11-06.\nArjun: I will prepare the demo by 2026-10-30.'
    action=dict(title='Prepare demo',owner='Arjun',due_date='2026-10-30',description='Prepare a working launch demo.',evidence='Arjun: I will prepare the demo by 2026-10-30.')
    decision=dict(topic='launch date',statement='Launch on 2026-11-06.',value='2026-11-06',owner='Maya',due_date='',evidence='Maya: Decision: launch date is 2026-11-06.')
    analysis=dict(summary='Launch agreed; demo assigned.',speakers=['Maya','Arjun'],decisions=[decision],actions=[action],warnings=[],engine='fictional-fixture')
    mid=store.save_meeting('Fictional release review',transcript,'2026-10-31',analysis)
    store.approve_meeting(mid,[action],{})
    task=store.list_actions()[0]
    missing=dict(title='Confirm accessibility checklist',owner='',due_date=None,description='Confirm the checklist.',evidence='Leena: Action: confirm accessibility checklist.')
    gap_mid=store.save_meeting('Fictional incomplete follow-up','Leena: Action: confirm accessibility checklist.','2026-10-31',dict(summary='Checklist needs details.',speakers=['Leena'],decisions=[],actions=[missing],warnings=[],engine='fictional-fixture'))
    sources=workspace_sources(store)
    for mode in MODES:
        query={'Ask your meetings':'What is the launch date? Give one concise answer.', 'Meeting brief':'Give one agenda item for the next launch meeting.', 'Clarify missing details':'Ask for missing details on the accessibility checklist. Give one question.', 'Follow-up draft':'Draft one short paragraph about the approved launch decision.', 'Break down a task':'Suggest two practical steps for preparing the demo.', 'Risk suggestions':'Suggest one possible delivery concern and explain uncertainty.'}[mode]
        started=time.monotonic()
        try:
            chosen=select_sources(sources,query,mode,gap_mid if mode=='Clarify missing details' else mid,task['id'])
            result=assist(mode,query,chosen,model='qwen3:1.7b',as_of='2026-10-31')
            row=dict(mode=mode,seconds=round(time.monotonic()-started,1),supported_items=len(result['items']),result=result)
        except Exception as error:
            row=dict(mode=mode,error=str(error))
        report.append(row)
        Path('data/assistant-live-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in row.items() if k!='result'}),flush=True)
assert all(r.get('supported_items',0)>0 for r in report), 'Some modes did not return a supported item; inspect live report.'
