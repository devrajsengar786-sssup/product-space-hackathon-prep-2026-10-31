"""Optional live local-AI rehearsal using explicitly fictional meeting data."""
from pathlib import Path
import json
import os
import tempfile
import time
from decisiondesk.analysis import analyze_transcript
from decisiondesk.store import Store
from decisiondesk.workspaces import Workspaces
from decisiondesk.integrations import issue_body

ROOT=Path(__file__).resolve().parent
PLANNING='Maya: Decision: launch date is 2026-11-06.\nArjun: I will prepare the demo by 2026-11-03.'
FOLLOWUP='Maya: Decision: launch date is 2026-11-08, actually 2026-11-09.\nArjun: I will update the demo by 2026-11-04.'

def main():
    report={'fictional':True,'model':'qwen3:1.7b','checks':[]}
    results=[]
    for text in (PLANNING,FOLLOWUP):
        start=time.monotonic()
        result=analyze_transcript(text,'2026-10-31',engine='ollama',model=report['model'])
        results.append(result)
        print('Local AI extraction completed in',round(time.monotonic()-start,1),'seconds',flush=True)
    first,second=results
    assert any(d['value']=='2026-11-06' for d in first['decisions']), 'First launch decision needs review'
    assert any(d['value']=='2026-11-09' for d in second['decisions']), 'Spoken correction needs review'
    assert any(a['owner']=='Arjun' and a['due_date']=='2026-11-04' for a in second['actions']), 'Action owner/date needs review'
    with tempfile.TemporaryDirectory(prefix='decisiondesk-rehearsal-') as temp:
        store=Store(Path(temp)/'test.sqlite3')
        one=store.save_meeting('Fictional planning',PLANNING,'2026-10-31',first)
        assert not store.list_decisions()
        store.approve_meeting(one,first['actions'],{})
        two=store.save_meeting('Fictional follow-up',FOLLOWUP,'2026-10-31',second)
        conflicts=store.find_conflicts(second['decisions']);assert conflicts,'Expected launch-date conflict'
        try:store.approve_meeting(two,second['actions'],{})
        except ValueError:pass
        else:raise AssertionError('Conflict approved without resolution')
        store.approve_meeting(two,second['actions'],{str(c['proposed_index']):'replace' for c in conflicts})
        assert any(d['value']=='2026-11-09' for d in store.list_decisions())
        task=store.list_actions(two)[0];store.update_action_status(task['id'],'done')
        assert store.weekly_digest('2026-10-31')
        assert len(store.decision_timeline())>=2
        restored=Store(Path(temp)/'restored.sqlite3');restored.restore_backup(store.export_backup())
        assert len(restored.list_meetings())==2
    report['checks']=['live AI extraction','spoken correction','drafts do not change memory','cross-meeting conflict','unresolved approval blocked','explicit replacement','task completion','weekly digest','decision history','backup restore']
    base=Path(os.environ.get('DECISIONDESK_DB_PATH',str(ROOT/'data'/'decisiondesk.sqlite3')))
    catalog=Workspaces(base);name='Demo rehearsal — fictional'
    existing=next((w for w in catalog.list() if w['name']==name),None)
    wid=existing['id'] if existing else catalog.create(name)
    demo=Store(catalog.path(wid))
    if not demo.list_meetings():
        mid=demo.save_meeting('Fictional Atlas planning · seeded rehearsal fixture',PLANNING,'2026-10-31',first)
        demo.approve_meeting(mid,first['actions'],{})
        task=next(a for a in demo.list_actions(mid) if a['owner']=='Arjun')
        demo.edit_action(task['id'],title='[DEMO] Prepare Atlas demo (fictional)',owner='Arjun',due_date=task['due_date'],description='Fictional hackathon demonstration task. This is a seeded rehearsal fixture; no real project work is assigned.')
    report.update(workspace=wid,workspace_name=name,workspace_path=str(demo.path),planning=PLANNING,followup=FOLLOWUP)
    task=next((a for a in demo.list_actions() if a['title']=='[DEMO] Prepare Atlas demo (fictional)'),None)
    if task:report['tracker_preview']={'repository':'devrajsengar786-sssup/product-space-hackathon-prep-2026-10-31','action_id':task['id'],'title':task['title'],'body':issue_body(task)}
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data'/'demo-rehearsal-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('PASS:',', '.join(report['checks']),flush=True)
    print('Prepared isolated workspace:',name,flush=True)

if __name__=='__main__':main()
