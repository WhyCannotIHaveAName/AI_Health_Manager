import json
import sqlite3
import uuid
from datetime import datetime, timedelta, date
from pathlib import Path
from .domain import validate_record


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, day TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, updated TEXT NOT NULL)")
        self.db.execute("CREATE INDEX IF NOT EXISTS records_day ON records(day)")
        self.db.execute("PRAGMA user_version=1")
        self.db.commit()

    def save(self, record, record_id=None):
        clean = validate_record(record)
        record_id = record_id or uuid.uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO records VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET day=excluded.day,kind=excluded.kind,payload=excluded.payload,updated=excluded.updated",
                            (record_id, clean["day"], clean["kind"], json.dumps(clean, ensure_ascii=False), datetime.now().isoformat()))
        return record_id

    def records(self, since=None, until=None):
        rows = self.db.execute("SELECT id,payload FROM records WHERE day>=? AND day<=? ORDER BY day DESC,updated DESC",
                               (since or "1900-01-01", until or date.today().isoformat())).fetchall()
        return [dict(json.loads(payload), id=record_id) for record_id, payload in rows]

    def delete(self, record_id):
        with self.db:
            self.db.execute("DELETE FROM records WHERE id=?", (record_id,))

    def recent(self, days=14):
        return self.records((date.today() - timedelta(days=days-1)).isoformat())

    def export_data(self):
        return {"format": "ai-health-manager", "version": 1, "records": self.records()}

    def import_data(self, data):
        if not isinstance(data, dict) or data.get("format") != "ai-health-manager" or data.get("version") != 1:
            raise ValueError("请选择本应用导出的 v1 JSON 备份")
        rows = data.get("records")
        if not isinstance(rows, list) or len(rows) > 50000:
            raise ValueError("备份最多支持 50000 条记录")
        # Validate the entire backup before the transaction; IDs never become SQL.
        checked = []
        seen = set()
        for row in rows:
            clean = validate_record(row)
            rid = str(row.get("id", ""))
            if len(rid) != 32 or any(c not in "0123456789abcdef" for c in rid) or rid in seen:
                raise ValueError("备份中的记录 ID 无效或重复")
            seen.add(rid)
            checked.append((rid, clean["day"], clean["kind"], json.dumps(clean, ensure_ascii=False), datetime.now().isoformat()))
        before = self.db.total_changes
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO records VALUES (?,?,?,?,?)", checked)
        return self.db.total_changes - before

    def close(self):
        self.db.close()
