"""Durable, workspace-local live notes and a resumable meeting clock."""
from contextlib import contextmanager
from datetime import date
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit

FIELDS={'title':150,'agenda':6000,'participants':2000,'notes':30000,'call_url':2000}

def call_url(value):
    value=str(value or '').strip()
    if not value:return ''
    try:
        url=urlsplit(value);host=(url.hostname or '').lower()
        trusted=any(host==domain or host.endswith('.'+domain) for domain in ('zoom.us','meet.google.com','teams.microsoft.com','teams.live.com'))
        if url.scheme!='https' or not trusted or url.username or url.password or url.port not in (None,443):raise ValueError()
    except ValueError:raise ValueError('Use an existing HTTPS Zoom, Google Meet or Microsoft Teams meeting link.') from None
    return value


def elapsed(row,now=None):
    now=time.time() if now is None else now
    return row['elapsed_seconds']+(max(0,now-row['running_since']) if row['status']=='running' else 0)


def export_notes(row):
    return f"# {row['title']}\n\nDate: {row['meeting_date']}\nParticipants: {row['participants'] or 'Not entered'}\nStatus: {row['status']}\nElapsed: {int(elapsed(row))//60} minutes\n\n## Agenda\n{row['agenda']}\n\n## Meeting notes\n{row['notes']}\n"


class LiveMeetings:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS live_meetings(id INTEGER PRIMARY KEY,title TEXT NOT NULL,
                agenda TEXT NOT NULL DEFAULT '',participants TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',
                call_url TEXT NOT NULL DEFAULT '',meeting_date TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ready',
                elapsed_seconds REAL NOT NULL DEFAULT 0,running_since REAL,version INTEGER NOT NULL DEFAULT 1)''')
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()
    def create(self,title,meeting_date):
        title=str(title).strip()
        if not title or len(title)>150:raise ValueError('Enter a meeting title, up to 150 characters.')
        day=date.fromisoformat(str(meeting_date)).isoformat()
        with self.db() as db:
            return db.execute('INSERT INTO live_meetings(title,meeting_date) VALUES(?,?)',(title,day)).lastrowid
    def list(self):
        with self.db() as db:return [dict(row) for row in db.execute('SELECT * FROM live_meetings ORDER BY id DESC')]
    def get(self,identifier):
        with self.db() as db:row=db.execute('SELECT * FROM live_meetings WHERE id=?',(identifier,)).fetchone()
        if row is None:raise ValueError('Live meeting not found.')
        return dict(row)
    def _current(self,db,identifier,version):
        row=db.execute('SELECT * FROM live_meetings WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('Live meeting not found.')
        if row['version']!=version:raise ValueError('This meeting changed in another tab. Download your local notes, then reload the saved version.')
        return dict(row)
    def save(self,identifier,version,**fields):
        if set(fields)!=set(FIELDS):raise ValueError('Use all live meeting fields.')
        fields={key:str(value).strip() for key,value in fields.items()}
        if not fields['title'] or any(len(fields[key])>limit for key,limit in FIELDS.items()):raise ValueError('Check the title and field length limits. Notes can contain up to 30,000 characters.')
        fields['call_url']=call_url(fields['call_url'])
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE');row=self._current(db,identifier,version)
            if row['status']=='ended':raise ValueError('Finished meeting notes are read-only. Create a new live meeting for another session.')
            db.execute('UPDATE live_meetings SET title=?,agenda=?,participants=?,notes=?,call_url=?,version=version+1 WHERE id=?',tuple(fields[k] for k in FIELDS)+(identifier,))
        return self.get(identifier)
    def transition(self,identifier,version,event,now=None):
        now=time.time() if now is None else now
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE');row=self._current(db,identifier,version)
            allowed={'start':('ready',),'pause':('running',),'resume':('paused',),'finish':('ready','running','paused')}
            if event not in allowed or row['status'] not in allowed[event]:raise ValueError('That clock action is not available in the current meeting state.')
            status={'start':'running','pause':'paused','resume':'running','finish':'ended'}[event]
            seconds=elapsed(row,now)
            db.execute('UPDATE live_meetings SET status=?,elapsed_seconds=?,running_since=?,version=version+1 WHERE id=?',(status,seconds,now if status=='running' else None,identifier))
        return self.get(identifier)
