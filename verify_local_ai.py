import json
from pathlib import Path
import time
from decisiondesk.analysis import analyze_transcript, available_local_models
text='Maya: Decision: launch date is 2026-11-06.\nArjun: I will prepare the demo by 2026-11-03.'
started=time.monotonic()
models=available_local_models()
assert 'qwen3:1.7b' in models, 'Model not installed yet'
result=analyze_transcript(text,'2026-10-31',engine='ollama',model='qwen3:1.7b')
report={'verified_at':'2026-10-31','elapsed_seconds':round(time.monotonic()-started,1),'models':models,'fictional_transcript':text,'result':result}
Path('data/local-ai-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
assert result['engine']=='ollama:qwen3:1.7b'
assert any(a['owner']=='Arjun' and a['due_date']=='2026-11-03' for a in result['actions']), 'Review model extraction quality'
assert len(result['decisions'])==1 and len(result['actions'])==1, 'Model mixed up decision and task categories'
Path('data/preferences.json').write_text(json.dumps({'engine':'ollama','model':'qwen3:1.7b'}),encoding='utf-8')
print(json.dumps(report,indent=2))
