"""Small SQLite repository with tracked SQL migrations.

The prototype intentionally uses the stdlib sqlite3 module: the persisted
records are plain JSON documents and this keeps the schema easy to inspect and
replace when an institution supplies its own adapter.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"), default=str)


def _load(v: str | None, default: Any = None) -> Any:
    if v is None:
        return default
    try: return json.loads(v)
    except (TypeError, ValueError): return default


class SQLiteRepository:
    def __init__(self, path: str | Path | None = None):
        default_path = Path(__file__).resolve().parents[3] / "data" / "runtime" / "prototype.db"
        self.path = Path(path) if path is not None else default_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self.migrate()

    def migrate(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
                );
            """)
            current = self._conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0]
            migrations = {1: """
                CREATE TABLE IF NOT EXISTS cases (
                  case_id TEXT PRIMARY KEY, current_revision INTEGER NOT NULL,
                  case_json TEXT NOT NULL, raw_payload TEXT NOT NULL,
                  warnings_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS case_revisions (
                  case_id TEXT NOT NULL, revision INTEGER NOT NULL,
                  case_json TEXT NOT NULL, raw_payload TEXT NOT NULL,
                  warnings_json TEXT NOT NULL, created_at TEXT NOT NULL,
                  PRIMARY KEY(case_id, revision), FOREIGN KEY(case_id) REFERENCES cases(case_id)
                );
                CREATE TABLE IF NOT EXISTS runs (
                  run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, mode TEXT NOT NULL,
                  provider_kind TEXT NOT NULL, request_id TEXT, previous_run_id TEXT,
                  status TEXT NOT NULL, run_json TEXT NOT NULL, created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL, UNIQUE(case_id, request_id),
                  FOREIGN KEY(case_id) REFERENCES cases(case_id)
                );
                CREATE TABLE IF NOT EXISTS node_executions (
                  run_id TEXT NOT NULL, node_id TEXT NOT NULL, node_json TEXT NOT NULL,
                  PRIMARY KEY(run_id,node_id), FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS rule_evaluations (
                  run_id TEXT NOT NULL, evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  evaluation_json TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS evidence_snapshots (
                  run_id TEXT NOT NULL, snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  evidence_json TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS reviews (
                  review_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, action TEXT NOT NULL,
                  review_json TEXT NOT NULL, created_at TEXT NOT NULL,
                  FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                  event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
                  subject_id TEXT, event_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                  benchmark_id TEXT PRIMARY KEY, request_id TEXT UNIQUE, benchmark_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS benchmark_results (
                  benchmark_id TEXT NOT NULL, result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  result_json TEXT NOT NULL, FOREIGN KEY(benchmark_id) REFERENCES benchmark_runs(benchmark_id)
                );
            """}
            for version, sql in migrations.items():
                if version > current:
                    self._conn.executescript(sql)
                    self._conn.execute("INSERT INTO schema_migrations VALUES (?,?)", (version, _now()))

    def close(self):
        with self._lock: self._conn.close()

    def recover_running(self) -> int:
        with self._lock, self._conn:
            rows = self._conn.execute("SELECT run_id,run_json FROM runs WHERE status='running'").fetchall()
            for row in rows:
                obj = _load(row["run_json"], {})
                obj.update(status="failed", error={"code":"INTERRUPTED", "detail":"服務重啟時執行被中斷"})
                self._conn.execute("UPDATE runs SET status='failed',run_json=?,updated_at=? WHERE run_id=?", (_dump(obj), _now(), row["run_id"]))
            return len(rows)

    def upsert_case(self, case: dict[str, Any], raw_payload: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
        cid = case["case_id"]
        with self._lock, self._conn:
            old = self._conn.execute("SELECT current_revision FROM cases WHERE case_id=?", (cid,)).fetchone()
            revision = (old[0] + 1) if old else 1
            now = _now()
            if old:
                self._conn.execute("UPDATE cases SET current_revision=?,case_json=?,raw_payload=?,warnings_json=?,updated_at=? WHERE case_id=?", (revision,_dump(case),_dump(raw_payload),_dump(warnings),now,cid))
            else:
                self._conn.execute("INSERT INTO cases VALUES (?,?,?,?,?,?,?)", (cid,revision,_dump(case),_dump(raw_payload),_dump(warnings),now,now))
            self._conn.execute("INSERT INTO case_revisions VALUES (?,?,?,?,?,?)", (cid,revision,_dump(case),_dump(raw_payload),_dump(warnings),now))
            self._audit("case.imported", cid, {"revision": revision, "warnings": warnings})
        return self.get_case(cid) or {}

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        return self._case_row(row) if row else None

    def list_cases(self) -> list[dict[str, Any]]:
        return [self._case_row(r) for r in self._conn.execute("SELECT * FROM cases ORDER BY case_id")]

    def list_revisions(self, case_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM case_revisions WHERE case_id=? ORDER BY revision", (case_id,)).fetchall()
        return [{"case_id":r["case_id"],"revision":r["revision"],"case":_load(r["case_json"],{}),"raw_payload":_load(r["raw_payload"],{}),"warnings":_load(r["warnings_json"],[]),"created_at":r["created_at"]} for r in rows]

    def _case_row(self, r: sqlite3.Row) -> dict[str, Any]:
        return {"case_id":r["case_id"],"revision":r["current_revision"],"case":_load(r["case_json"],{}),"raw_payload":_load(r["raw_payload"],{}),"warnings":_load(r["warnings_json"],[])}

    def create_run(self, run_id: str, case_id: str, mode: str, provider_kind: str, request_id: str | None, previous_run_id: str | None, run: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        with self._lock, self._conn:
            if request_id:
                old = self._conn.execute("SELECT run_json FROM runs WHERE case_id=? AND request_id=?", (case_id,request_id)).fetchone()
                if old: return _load(old[0], {})
            self._conn.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)", (run_id,case_id,mode,provider_kind,request_id,previous_run_id,run.get("status","running"),_dump(run),now,now))
        return run

    def save_run(self, run_id: str, run: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            self._conn.execute("UPDATE runs SET status=?,run_json=?,updated_at=? WHERE run_id=?", (run.get("status","failed"),_dump(run),_now(),run_id))
            self._conn.execute("DELETE FROM node_executions WHERE run_id=?", (run_id,))
            for node in run.get("nodes",[]) or []: self._conn.execute("INSERT OR REPLACE INTO node_executions VALUES (?,?,?)", (run_id,node.get("node_id",node.get("id","unknown")),_dump(node)))
            self._conn.execute("DELETE FROM rule_evaluations WHERE run_id=?", (run_id,))
            for item in run.get("rule_evaluations",[]) or []: self._conn.execute("INSERT INTO rule_evaluations(run_id,evaluation_json) VALUES (?,?)", (run_id,_dump(item)))
            self._conn.execute("DELETE FROM evidence_snapshots WHERE run_id=?", (run_id,))
            for item in run.get("evidence_snapshots",[]) or []: self._conn.execute("INSERT INTO evidence_snapshots(run_id,evidence_json) VALUES (?,?)", (run_id,_dump(item)))
        return run

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT run_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return _load(row[0], {}) if row else None

    def list_runs(self, case_id: str | None = None) -> list[dict[str, Any]]:
        if case_id:
            rows = self._conn.execute("SELECT run_json FROM runs WHERE case_id=? ORDER BY created_at DESC", (case_id,)).fetchall()
        else: rows = self._conn.execute("SELECT run_json FROM runs ORDER BY created_at DESC").fetchall()
        return [_load(r[0], {}) for r in rows]

    def add_review(self, review_id: str, run_id: str, action: str, review: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            self._conn.execute("INSERT INTO reviews VALUES (?,?,?,?,?)", (review_id,run_id,action,_dump(review),_now()))
            self._audit("review.created", review_id, {"run_id":run_id,"action":action})
        return review

    def list_reviews(self, run_id: str | None = None) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT review_json FROM reviews WHERE (? IS NULL OR run_id=?) ORDER BY created_at", (run_id,run_id)).fetchall()
        return [_load(r[0], {}) for r in rows]

    def save_benchmark(self, benchmark_id: str, request_id: str | None, obj: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock, self._conn:
            self._conn.execute("INSERT INTO benchmark_runs VALUES (?,?,?,?)", (benchmark_id,request_id,_dump(obj),_now()))
            for r in results: self._conn.execute("INSERT INTO benchmark_results(benchmark_id,result_json) VALUES (?,?)", (benchmark_id,_dump(r)))
        return obj

    def list_benchmarks(self) -> list[dict[str, Any]]:
        return [_load(r[0],{}) for r in self._conn.execute("SELECT benchmark_json FROM benchmark_runs ORDER BY created_at DESC")]

    def get_benchmark(self, benchmark_id: str) -> dict[str, Any] | None:
        r=self._conn.execute("SELECT benchmark_json FROM benchmark_runs WHERE benchmark_id=?",(benchmark_id,)).fetchone()
        return _load(r[0],{}) if r else None

    def _audit(self, event_type: str, subject_id: str, payload: dict[str,Any]):
        self._conn.execute("INSERT INTO audit_events(event_type,subject_id,event_json,created_at) VALUES (?,?,?,?)", (event_type,subject_id,_dump(payload),_now()))
