import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


DEFAULT_BRAND = {
    'name': 'NovaFlow AI', 'product': 'AI marketing automation for lean teams',
    'audience': 'Startup founders and small marketing teams',
    'positioning': 'Connect your brand, weekly plan, content and insights in one affordable workspace.',
    'voice': 'Clear, practical, confident. Short sentences. Explain the why.',
    'cta': 'Book a product walkthrough', 'website': '',
    'banned_words': 'guaranteed, revolutionary', 'monthly_budget': 300,
}


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                    data TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS records_kind ON records(kind);
                CREATE UNIQUE INDEX IF NOT EXISTS metric_identity ON records(json_extract(data,'$.date'),json_extract(data,'$.channel'),json_extract(data,'$.campaign')) WHERE kind='metric';
                CREATE UNIQUE INDEX IF NOT EXISTS plan_asset_identity ON records(json_extract(data,'$.plan_id'),json_extract(data,'$.plan_index')) WHERE kind='asset' AND json_extract(data,'$.plan_id') IS NOT NULL;
                CREATE TABLE IF NOT EXISTS usage (
                    id INTEGER PRIMARY KEY, day TEXT NOT NULL, task TEXT NOT NULL,
                    mode TEXT NOT NULL, state TEXT NOT NULL, tokens INTEGER NOT NULL DEFAULT 0);
            ''')
            db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('brand', json.dumps(DEFAULT_BRAND)))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def brand(self):
        with self.connect() as db:
            return json.loads(db.execute('SELECT value FROM settings WHERE key=?', ('brand',)).fetchone()[0])

    def save_brand(self, brand):
        with self.connect() as db:
            db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(brand), 'brand'))
        return brand

    @staticmethod
    def unpack(row):
        if row is None:
            return None
        return {**json.loads(row['data']), 'id': row['id'], 'revision': row['revision'],
                'created_at': row['created_at'], 'updated_at': row['updated_at']}

    def list(self, kind):
        with self.connect() as db:
            return [self.unpack(r) for r in db.execute('SELECT * FROM records WHERE kind=? ORDER BY id DESC', (kind,))]

    def get(self, kind, record_id):
        with self.connect() as db:
            return self.unpack(db.execute('SELECT * FROM records WHERE kind=? AND id=?', (kind, record_id)).fetchone())

    def create(self, kind, data):
        stamp = now()
        with self.connect() as db:
            cur = db.execute('INSERT INTO records(kind,data,created_at,updated_at) VALUES (?,?,?,?)',
                             (kind, json.dumps(data), stamp, stamp))
            record_id = cur.lastrowid
        return self.get(kind, record_id)

    def update(self, kind, record_id, data, revision):
        # Compare-and-swap protects approval against stale editor tabs.
        data = {k: v for k, v in data.items() if k not in ('id', 'revision', 'created_at', 'updated_at')}
        with self.connect() as db:
            cur = db.execute('UPDATE records SET data=?, revision=revision+1, updated_at=? WHERE kind=? AND id=? AND revision=?',
                             (json.dumps(data), now(), kind, record_id, revision))
            if cur.rowcount != 1:
                raise ValueError('This record changed in another tab. Reload and try again.')
        return self.get(kind, record_id)
