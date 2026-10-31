"""Workspace features shared by the local store; no network operations."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
import sqlite3
import uuid


def iso_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class WorkspaceFeatures:
    def _upgrade_features(self, db):
        columns = {row[1] for row in db.execute('PRAGMA table_info(actions)')}
        if 'priority' not in columns:
            db.execute("ALTER TABLE actions ADD COLUMN priority TEXT NOT NULL DEFAULT 'Normal'")
        db.executescript('''
            CREATE TABLE IF NOT EXISTS dependencies(
              action_id INTEGER REFERENCES actions(id), depends_on INTEGER REFERENCES actions(id),
              PRIMARY KEY(action_id,depends_on), CHECK(action_id!=depends_on));
            CREATE TABLE IF NOT EXISTS activity(
              id INTEGER PRIMARY KEY, kind TEXT NOT NULL, record_id INTEGER,
              detail TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')

    def _event(self, db, kind, record_id, detail):
        db.execute('INSERT INTO activity(kind,record_id,detail,created_at) VALUES(?,?,?,?)',
                   (kind, record_id, json.dumps(detail), iso_now()))

    def _unresolved_dependencies(self, db, action_id):
        return [dict(r) for r in db.execute('''SELECT a.* FROM dependencies d
            JOIN actions a ON a.id=d.depends_on WHERE d.action_id=? AND a.status!='done' ''', (action_id,))]

    def decorate_actions(self, actions):
        with self._connection() as db:
            for action in actions:
                action['dependencies'] = [r[0] for r in db.execute('SELECT depends_on FROM dependencies WHERE action_id=?', (action['id'],))]
                action['blocked_by'] = self._unresolved_dependencies(db, action['id'])
        return actions

    def edit_action(self, action_id, *, title, owner, due_date, description, priority='Normal', dependencies=()):
        if priority not in ('Low', 'Normal', 'High', 'Urgent'):
            raise ValueError('Choose a valid priority.')
        if not str(title).strip() or not str(owner).strip() or str(owner).casefold()=='unassigned':
            raise ValueError('A title and named owner are required.')
        try:
            due_date = date.fromisoformat(str(due_date)).isoformat()
        except ValueError:
            raise ValueError('Choose a valid deadline.') from None
        ids = list(dependencies)
        if any(type(i) is not int for i in ids) or len(set(ids)) != len(ids) or action_id in ids:
            raise ValueError('Dependencies must be distinct other tasks.')
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            action = db.execute('SELECT * FROM actions WHERE id=?', (action_id,)).fetchone()
            if not action or action['status']=='draft':
                raise ValueError('Approve this task in its meeting before editing it here.')
            graph = {}
            for r in db.execute('SELECT * FROM dependencies'):
                graph.setdefault(r['action_id'], []).append(r['depends_on'])
            graph[action_id] = ids
            def reaches(start, target, seen):
                pending=[start]
                while pending:
                    node=pending.pop()
                    if node==target:
                        return True
                    if node not in seen:
                        seen.add(node)
                        pending.extend(graph.get(node,[]))
                return False
            for dep in ids:
                row = db.execute('SELECT * FROM actions WHERE id=?', (dep,)).fetchone()
                if not row or row['status']=='draft':
                    raise ValueError('Dependencies must be approved tasks in this workspace.')
                if reaches(dep, action_id, set()):
                    raise ValueError('That dependency would create a cycle.')
                if action['status']=='done' and row['status']!='done':
                    raise ValueError('Reopen the completed task before adding an unfinished dependency.')
            db.execute('UPDATE actions SET title=?,owner=?,due_date=?,description=?,priority=?,updated_at=? WHERE id=?',
                       (str(title).strip()[:500],str(owner).strip()[:300],due_date,str(description)[:6000],priority,iso_now(),action_id))
            db.execute('DELETE FROM dependencies WHERE action_id=?', (action_id,))
            db.executemany('INSERT INTO dependencies VALUES(?,?)', [(action_id,i) for i in ids])
            self._event(db,'task_edited',action_id,{'title':title,'priority':priority,'dependencies':ids})

    def decision_timeline(self):
        with self._connection() as db:
            rows = [dict(r) for r in db.execute('''SELECT d.*, m.title AS meeting_title,m.meeting_date
              FROM decisions d JOIN meetings m ON m.id=d.meeting_id ORDER BY d.id''')]
        previous = {}
        for row in rows:
            row['previous_value'] = previous.get(row['topic_key'])
            previous[row['topic_key']] = row['value']
        return rows[::-1]

    def search(self, query, kind='All'):
        query = str(query).strip().casefold()
        if len(query)<2:
            return []
        with self._connection() as db:
            records=[]
            if kind in ('All','Meetings'):
                for r in db.execute('SELECT * FROM meetings ORDER BY id DESC'):
                    records.append(dict(kind='Meeting', id=r['id'], meeting_id=r['id'], title=r['title'], text=r['transcript'], date=r['meeting_date'], status=r['status']))
            if kind in ('All','Decisions'):
                for r in db.execute('SELECT * FROM decisions ORDER BY id DESC'):
                    records.append(dict(kind='Decision', id=r['id'], meeting_id=r['meeting_id'], title=r['topic'], text=r['statement']+'\n'+r['evidence'], date=r['created_at'][:10], status='Current' if r['active'] else 'Superseded'))
            if kind in ('All','Tasks'):
                for r in db.execute('SELECT * FROM actions ORDER BY id DESC'):
                    records.append(dict(kind='Task', id=r['id'], meeting_id=r['meeting_id'], title=r['title'], text=r['owner']+'\n'+r['description']+'\n'+r['evidence'], date=r['due_date'] or '', status=r['status']))
        matches=[]
        for r in records:
            haystack = r['title']+'\n'+r['text']
            index = haystack.casefold().find(query)
            if index>=0:
                r['snippet']=haystack[max(0,index-65):index+230]
                matches.append(r)
        return matches[:200]

    def changes_since_last_meeting(self):
        meetings = self.list_meetings()
        if not meetings:
            return {'meeting':None,'decisions':[],'actions':[],'completed':[]}
        newest = meetings[0]
        decisions = [d for d in self.decision_timeline() if d['meeting_id']==newest['id']]
        completed = [a for a in self.list_actions() if a['status']=='done' and a['updated_at']>=newest['created_at']]
        return dict(meeting=newest, decisions=decisions, actions=self.list_actions(newest['id']), completed=completed)

    def analytics(self, as_of):
        actions=self.decorate_actions(self.list_actions())
        accepted=[a for a in actions if a['status']!='draft']
        completed=[a for a in accepted if a['status']=='done']
        people={}
        for a in accepted:
            p=people.setdefault(a['owner'],dict(Owner=a['owner'],Open=0,Completed=0,Overdue=0,Blocked=0))
            p['Completed' if a['status']=='done' else 'Open']+=1
            p['Overdue']+=int(a['status']!='done' and bool(a['due_date']) and a['due_date']<as_of)
            p['Blocked']+=int(a['status']!='done' and bool(a['blocked_by']))
        return dict(total=len(accepted), completed=len(completed), completion_rate=round(100*len(completed)/len(accepted)) if accepted else 0,
                    blocked=sum(bool(a['blocked_by']) and a['status']!='done' for a in accepted), people=list(people.values()))

    def export_backup(self):
        with self._connection() as db:
            tables={table:[dict(r) for r in db.execute('SELECT * FROM '+table)] for table in ('meetings','decisions','actions','publication_attempts','dependencies','activity')}
        return json.dumps(dict(format='decisiondesk-workspace',version=1,exported_at=iso_now(),tables=tables),ensure_ascii=False,indent=2)

    def restore_backup(self, content):
        """Restore validated data only into an empty workspace, atomically."""
        if len(content)>20_000_000:
            raise ValueError('Backup exceeds the 20 MB limit.')
        try:
            data=json.loads(content)
        except (ValueError,TypeError):
            raise ValueError('This is not a valid JSON backup.') from None
        tables=('meetings','decisions','actions','publication_attempts','dependencies','activity')
        if not isinstance(data,dict) or data.get('format')!='decisiondesk-workspace' or data.get('version')!=1 or set(data.get('tables',{}))!=set(tables):
            raise ValueError('Use a DecisionDesk workspace backup (version 1).')
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if any(db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables):
                raise ValueError('Restore into a new, empty workspace so existing work is preserved.')
            try:
                for table in tables:
                    cols=[r[1] for r in db.execute('PRAGMA table_info('+table+')')]
                    rows=data['tables'][table]
                    if not isinstance(rows,list) or len(rows)>50000:
                        raise ValueError('Invalid backup table.')
                    for row in rows:
                        if not isinstance(row,dict) or set(row)!=set(cols):
                            raise ValueError('Invalid backup columns.')
                        if table=='meetings':
                            analysis=json.loads(row['analysis'])
                            if not isinstance(analysis,dict) or row['status'] not in ('draft','approved'):
                                raise ValueError('Invalid meeting record.')
                            if not all(isinstance(row[k],str) for k in ('title','transcript','meeting_date')):
                                raise ValueError('Invalid meeting text.')
                            date.fromisoformat(row['meeting_date'])
                            if not isinstance(analysis.get('summary'),str):
                                raise ValueError('Invalid meeting summary.')
                            for key in ('decisions','actions','speakers','warnings'):
                                if not isinstance(analysis.get(key),list):
                                    raise ValueError('Invalid meeting analysis.')
                            for key in ('speakers','warnings'):
                                if not all(isinstance(item,str) for item in analysis[key]):
                                    raise ValueError('Invalid analysis text.')
                            for key,fields in [('decisions',('topic','statement','value','owner','evidence')),('actions',('title','owner','description','evidence'))]:
                                for item in analysis[key]:
                                    if not isinstance(item,dict) or not all(isinstance(item.get(k),str) for k in fields):
                                        raise ValueError('Invalid analysis item.')
                                    if item.get('due_date'):
                                        date.fromisoformat(item['due_date'])
                        if table=='decisions':
                            if row['active'] not in (0,1) or not all(isinstance(row[k],str) for k in ('topic','topic_key','statement','value','owner','evidence')):
                                raise ValueError('Invalid decision record.')
                        if table=='actions':
                            if row['status'] not in ('draft','approved','published','done') or row['priority'] not in ('Low','Normal','High','Urgent'):
                                raise ValueError('Invalid task record.')
                            if not all(isinstance(row[k],str) for k in ('title','owner','description','evidence')):
                                raise ValueError('Invalid task text.')
                            if row['due_date']:
                                date.fromisoformat(row['due_date'])
                            url=row['external_url']
                            if url and not re.fullmatch(r'https://github\.com/[\w.-]+/[\w.-]+/issues/[1-9]\d*',url):
                                raise ValueError('Invalid issue URL.')
                        db.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',[row[c] for c in cols])
                if db.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('Backup has broken references.')
                # Validate restored dependency graph, including cycles.
                graph={}
                for r in db.execute('SELECT * FROM dependencies'):
                    graph.setdefault(r['action_id'],[]).append(r['depends_on'])
                indegree={n:0 for n in set(graph)|{c for children in graph.values() for c in children}}
                for children in graph.values():
                    for child in children:
                        indegree[child]+=1
                ready=[n for n,count in indegree.items() if count==0]
                visited=0
                while ready:
                    node=ready.pop();visited+=1
                    for child in graph.get(node,[]):
                        indegree[child]-=1
                        if indegree[child]==0:
                            ready.append(child)
                if visited!=len(indegree):
                    raise ValueError('Backup contains a dependency cycle.')
            except (sqlite3.Error,KeyError,TypeError,ValueError,RecursionError):
                raise ValueError('Backup validation failed. No data was restored.') from None


def calendar_export(actions):
    """All-day due-date events, stable UIDs, RFC 5545 CRLF and folded lines."""
    def esc(text):
        return str(text or '').replace('\\','\\\\').replace('\r','').replace('\n','\\n').replace(';','\\;').replace(',','\\,')
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//DecisionDesk//Tasks//EN','CALSCALE:GREGORIAN']
    for a in actions:
        if a['status'] not in ('approved','published') or not a.get('due_date'):
            continue
        day=date.fromisoformat(a['due_date'])
        uid=hashlib.sha256(f"{a['meeting_id']}:{a['id']}:{a['created_at']}".encode()).hexdigest()+'@decisiondesk.local'
        lines+=['BEGIN:VEVENT','UID:'+uid,'DTSTAMP:'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                'DTSTART;VALUE=DATE:'+day.strftime('%Y%m%d'),'DTEND;VALUE=DATE:'+(day+timedelta(days=1)).strftime('%Y%m%d'),
                'SUMMARY:'+esc(a['title']),'DESCRIPTION:'+esc('Owner: '+a['owner']+'\n'+a.get('description','')),'END:VEVENT']
    lines+=['END:VCALENDAR']
    folded=[]
    for line in lines:
        part=''
        for char in line:
            if len((part+char).encode('utf-8'))>74:
                folded.append(part);part=' '+char
            else:
                part+=char
        folded.append(part)
    return '\r\n'.join(folded)+'\r\n'
