"""Local workspace catalog with server-generated paths; no authentication fiction."""
from pathlib import Path
import sqlite3
import uuid
from contextlib import closing


class Workspaces:
    def __init__(self, default_path):
        self.default_path=Path(default_path)
        self.root=self.default_path.parent
        self.root.mkdir(parents=True,exist_ok=True)
        self.catalog=self.root/'workspace-catalog.sqlite3'
        with closing(sqlite3.connect(self.catalog)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE)')
            db.execute("INSERT OR IGNORE INTO workspaces VALUES('main','My workspace')")

    def list(self):
        with closing(sqlite3.connect(self.catalog)) as db, db:
            return [dict(id=r[0],name=r[1]) for r in db.execute("SELECT id,name FROM workspaces ORDER BY id!='main',name")]

    def create(self,name):
        name=str(name).strip()
        if not name or len(name)>80:
            raise ValueError('Use a workspace name between 1 and 80 characters.')
        identifier=uuid.uuid4().hex
        try:
            with closing(sqlite3.connect(self.catalog)) as db, db:
                db.execute('INSERT INTO workspaces VALUES(?,?)',(identifier,name))
        except sqlite3.IntegrityError:
            raise ValueError('A workspace with that name already exists.') from None
        return identifier

    def path(self,identifier):
        if identifier not in {w['id'] for w in self.list()}:
            raise ValueError('Unknown workspace.')
        return self.default_path if identifier=='main' else self.root/'workspaces'/f'{identifier}.sqlite3'
