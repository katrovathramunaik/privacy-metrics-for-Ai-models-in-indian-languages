"""SQLite database for storing test results and enabling resume capability."""

import sqlite3
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from contextlib import contextmanager

from .data_models import Language, DetectionResult, RecognitionResult, SensitiveItem, LookalikeItem


SCHEMA = """
-- Runs table: one row per execution run
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    command TEXT NOT NULL,
    config_hash TEXT,
    status TEXT DEFAULT 'running',  -- running, completed, failed, cancelled
    total_cost_usd REAL DEFAULT 0.0
);

-- Detection results (Test A)
CREATE TABLE IF NOT EXISTS detection_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    language TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    model_response TEXT NOT NULL,
    parsed_items TEXT,  -- JSON array
    unreadable BOOLEAN DEFAULT 0,
    tp_items TEXT,  -- JSON array
    fn_items TEXT,  -- JSON array
    fp_items TEXT,  -- JSON array
    tn_items TEXT,  -- JSON array
    prompt_tp BOOLEAN DEFAULT 0,
    prompt_fp BOOLEAN DEFAULT 0,
    prompt_fn BOOLEAN DEFAULT 0,
    prompt_tn BOOLEAN DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    UNIQUE(run_id, model_name, language, row_number)
);

-- Recognition results (Test B)
CREATE TABLE IF NOT EXISTS recognition_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    language TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    model_answer TEXT NOT NULL,
    judge_flagged BOOLEAN DEFAULT 0,
    judge_reason TEXT,
    prompt_tp BOOLEAN DEFAULT 0,
    prompt_fp BOOLEAN DEFAULT 0,
    prompt_fn BOOLEAN DEFAULT 0,
    prompt_tn BOOLEAN DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    UNIQUE(run_id, model_name, language, row_number)
);

-- Cost tracking
CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    request_type TEXT NOT NULL,  -- detection, recognition, judge
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_detection_run_model ON detection_results(run_id, model_name);
CREATE INDEX IF NOT EXISTS idx_recognition_run_model ON recognition_results(run_id, model_name);
CREATE INDEX IF NOT EXISTS idx_api_calls_run ON api_calls(run_id);
"""


class Database:
    """SQLite database manager for test results."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript(SCHEMA)
    
    @contextmanager
    def _get_conn(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def create_run(self, command: str, config_hash: str = "") -> str:
        """Create a new run and return run_id."""
        run_id = str(uuid.uuid4())[:12]
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, started_at, command, config_hash) VALUES (?, ?, ?, ?)",
                (run_id, datetime.utcnow().isoformat(), command, config_hash)
            )
        return run_id
    
    def complete_run(self, run_id: str, status: str = "completed", total_cost: float = 0.0):
        """Mark run as completed."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE runs SET completed_at = ?, status = ?, total_cost_usd = ? WHERE run_id = ?",
                (datetime.utcnow().isoformat(), status, total_cost, run_id)
            )
    
    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get run info."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            return dict(row) if row else None
    
    def get_latest_run(self, command: str) -> Optional[str]:
        """Get the latest run for a command (including completed)."""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT run_id FROM runs 
                WHERE command = ? 
                ORDER BY started_at DESC LIMIT 1""",
                (command,)
            ).fetchone()
            return row["run_id"] if row else None
    
    # Detection results
    def save_detection_result(self, run_id: str, result: DetectionResult):
        """Save or update a detection result."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO detection_results
                (run_id, model_name, language, row_number, prompt, model_response,
                 parsed_items, unreadable, tp_items, fn_items, fp_items, tn_items,
                 prompt_tp, prompt_fp, prompt_fn, prompt_tn)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                result.model_name,
                result.language.value,
                result.row_number,
                result.prompt,
                result.model_response,
                json.dumps(result.parsed_items, ensure_ascii=False),
                int(result.unreadable),
                json.dumps([item.to_dict() for item in result.tp_items], ensure_ascii=False),
                json.dumps([item.to_dict() for item in result.fn_items], ensure_ascii=False),
                json.dumps(result.fp_items, ensure_ascii=False),
                json.dumps([item.to_dict() for item in result.tn_items], ensure_ascii=False),
                int(result.prompt_tp),
                int(result.prompt_fp),
                int(result.prompt_fn),
                int(result.prompt_tn),
            ))
    
    def get_detection_results(self, run_id: str, model_name: Optional[str] = None,
                               language: Optional[Language] = None) -> List[DetectionResult]:
        """Load detection results from database."""
        query = "SELECT * FROM detection_results WHERE run_id = ?"
        params = [run_id]
        
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        if language:
            query += " AND language = ?"
            params.append(language.value)
        
        query += " ORDER BY model_name, language, row_number"
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        
        results = []
        for row in rows:
            result = DetectionResult(
                model_name=row["model_name"],
                language=Language(row["language"]),
                row_number=row["row_number"],
                prompt=row["prompt"],
                model_response=row["model_response"],
                parsed_items=json.loads(row["parsed_items"]) if row["parsed_items"] else [],
                unreadable=bool(row["unreadable"]),
                tp_items=[SensitiveItem.from_dict(item) for item in json.loads(row["tp_items"])] if row["tp_items"] else [],
                fn_items=[SensitiveItem.from_dict(item) for item in json.loads(row["fn_items"])] if row["fn_items"] else [],
                fp_items=json.loads(row["fp_items"]) if row["fp_items"] else [],
                tn_items=[LookalikeItem.from_dict(item) for item in json.loads(row["tn_items"])] if row["tn_items"] else [],
                prompt_tp=bool(row["prompt_tp"]),
                prompt_fp=bool(row["prompt_fp"]),
                prompt_fn=bool(row["prompt_fn"]),
                prompt_tn=bool(row["prompt_tn"]),
            )
            results.append(result)
        
        return results
    
    def get_completed_detection_keys(self, run_id: str) -> set:
        """Get set of (model_name, language, row_number) already completed."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT model_name, language, row_number FROM detection_results WHERE run_id = ?",
                (run_id,)
            ).fetchall()
        return {(r["model_name"], r["language"], r["row_number"]) for r in rows}
    
    # Recognition results
    def save_recognition_result(self, run_id: str, result: RecognitionResult):
        """Save or update a recognition result."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO recognition_results
                (run_id, model_name, language, row_number, prompt, model_answer,
                 judge_flagged, judge_reason, prompt_tp, prompt_fp, prompt_fn, prompt_tn)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                result.model_name,
                result.language.value,
                result.row_number,
                result.prompt,
                result.model_answer,
                int(result.judge_flagged),
                result.judge_reason,
                int(result.prompt_tp),
                int(result.prompt_fp),
                int(result.prompt_fn),
                int(result.prompt_tn),
            ))
    
    def get_recognition_results(self, run_id: str, model_name: Optional[str] = None,
                                 language: Optional[Language] = None) -> List[RecognitionResult]:
        """Load recognition results from database."""
        query = "SELECT * FROM recognition_results WHERE run_id = ?"
        params = [run_id]
        
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        if language:
            query += " AND language = ?"
            params.append(language.value)
        
        query += " ORDER BY model_name, language, row_number"
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        
        results = []
        for row in rows:
            result = RecognitionResult(
                model_name=row["model_name"],
                language=Language(row["language"]),
                row_number=row["row_number"],
                prompt=row["prompt"],
                model_answer=row["model_answer"],
                judge_flagged=bool(row["judge_flagged"]),
                judge_reason=row["judge_reason"] or "",
                prompt_tp=bool(row["prompt_tp"]),
                prompt_fp=bool(row["prompt_fp"]),
                prompt_fn=bool(row["prompt_fn"]),
                prompt_tn=bool(row["prompt_tn"]),
            )
            results.append(result)
        
        return results
    
    def get_completed_recognition_keys(self, run_id: str) -> set:
        """Get set of (model_name, language, row_number) already completed."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT model_name, language, row_number FROM recognition_results WHERE run_id = ?",
                (run_id,)
            ).fetchall()
        return {(r["model_name"], r["language"], r["row_number"]) for r in rows}
    
    # API call tracking
    def log_api_call(self, run_id: str, model_name: str, model_provider: str,
                     prompt_tokens: int, completion_tokens: int, cost_usd: float,
                     request_type: str):
        """Log an API call for cost tracking."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO api_calls
                (run_id, model_name, model_provider, prompt_tokens, completion_tokens,
                 total_tokens, cost_usd, request_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, model_name, model_provider,
                prompt_tokens, completion_tokens,
                prompt_tokens + completion_tokens, cost_usd, request_type
            ))
    
    def get_total_cost(self, run_id: str) -> float:
        """Get total cost for a run."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT SUM(cost_usd) as total FROM api_calls WHERE run_id = ?",
                (run_id,)
            ).fetchone()
        return row["total"] if row and row["total"] else 0.0
    
    def get_cost_summary(self, run_id: str) -> Dict[str, Any]:
        """Get cost breakdown by model."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT model_name, model_provider,
                       SUM(prompt_tokens) as prompt_tokens,
                       SUM(completion_tokens) as completion_tokens,
                       SUM(total_tokens) as total_tokens,
                       SUM(cost_usd) as total_cost,
                       COUNT(*) as call_count
                FROM api_calls WHERE run_id = ?
                GROUP BY model_name, model_provider
            """, (run_id,)).fetchall()
        
        summary = {}
        total = 0.0
        for row in rows:
            summary[row["model_name"]] = {
                "provider": row["model_provider"],
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "total_tokens": row["total_tokens"],
                "cost_usd": round(row["total_cost"], 4),
                "call_count": row["call_count"]
            }
            total += row["total_cost"]
        
        return {"by_model": summary, "total_usd": round(total, 4)}