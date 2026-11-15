"""Small SQLite state store; scientific raster cache lives separately on SSD."""

import json
import sqlite3
from datetime import datetime, timezone

from .settings import STATE


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path=None):
        self.path = path or STATE / "monitor.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id))"
            )

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def put(self, kind, key, value):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO records VALUES (?,?,?)",
                (kind, key, json.dumps(value, allow_nan=False)),
            )
        return value

    def get(self, kind, key):
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM records WHERE kind=? AND id=?", (kind, key)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, kind, key):
        with self.connect() as db:
            db.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, key))

    def all(self, kind):
        with self.connect() as db:
            rows = db.execute(
                "SELECT value FROM records WHERE kind=? ORDER BY rowid DESC", (kind,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
