"""Persistent job records and three independent, serial project queues.

Only task results and public metadata are persisted. Callables, credentials and
configuration snapshots stay in memory; unfinished work is marked interrupted
after a restart instead of silently repeating model calls or file writes.
"""
from collections import deque
import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Callable
from uuid import uuid4

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.core.log_system import redact
from Backend.core.protocol import to_wire


LANES = ("document", "image", "audio")
TERMINAL_STATES = frozenset(("succeeded", "partial", "failed", "cancelled", "interrupted"))


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _wire(value):
    # The same representation is used for notifications and SQLite. Isolate
    # records from service-owned mutable model/results returned by Future.
    return json.loads(json.dumps(to_wire(value), ensure_ascii=False, default=str))


@dataclass
class Job:
    id: str
    lane: str
    name: str
    source: str
    context: ExecutionContext = field(repr=False)
    project_id: str | None = None
    state: str = "queued"
    progress: dict = field(default_factory=dict)
    result: Any = None
    error: dict | None = None
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    updated_at: str = field(default_factory=_now)
    future: Future = field(default_factory=Future, repr=False)
    _scheduler: Any = field(default=None, repr=False)
    _worker_future: Future | None = field(default=None, repr=False)

    def to_dict(self):
        if self._scheduler is not None:
            with self._scheduler._lock:
                return self._record()
        return self._record()

    def _record(self, *, include_result=True):
        record = {
            "id": self.id, "job_id": self.id, "lane": self.lane,
            "name": self.name, "source": self.source, "project_id": self.project_id,
            "state": self.state, "progress": copy.deepcopy(self.progress),
            "error": copy.deepcopy(self.error),
            "created_at": self.created_at, "started_at": self.started_at,
            "finished_at": self.finished_at, "updated_at": self.updated_at,
        }
        if include_result:
            record["result"] = copy.deepcopy(self.result)
        return record


class JobScheduler:
    def __init__(self, path, on_event=None):
        self._lock = threading.RLock()
        self._event_lock = threading.Lock()
        self._events = deque()
        self._local = threading.local()
        self._jobs: dict[str, Job] = {}
        self._on_event = on_event
        self._closing = False
        self._closed = False
        self._close_done = threading.Event()
        if str(path) != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
            path = str(Path(path).expanduser())
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, lane TEXT NOT NULL, state TEXT NOT NULL,
            created_at TEXT NOT NULL, record TEXT NOT NULL, summary TEXT
        )""")
        columns = {column[1] for column in self._db.execute("PRAGMA table_info(jobs)")}
        if "summary" not in columns:
            # Do not deserialize every historical document during migration.
            # Old terminal rows get summaries lazily when they are listed.
            self._db.execute("ALTER TABLE jobs ADD COLUMN summary TEXT")
        self._db.execute("CREATE INDEX IF NOT EXISTS jobs_lane ON jobs(lane)")
        self._recover()
        self._pools = {
            lane: ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"job-{lane}")
            for lane in LANES
        }

    def _recover(self):
        placeholders = ",".join("?" for _ in TERMINAL_STATES)
        for identifier, payload in self._db.execute(
            f"SELECT id, record FROM jobs WHERE state NOT IN ({placeholders})", tuple(TERMINAL_STATES),
        ).fetchall():
            record = json.loads(payload)
            if record["state"] in TERMINAL_STATES:
                continue
            record.update(state="interrupted", finished_at=_now(), updated_at=_now(),
                          error={"code": "JOB_INTERRUPTED", "message": "后端退出前任务未完成，请确认项目状态后重新提交"})
            summary = {key: value for key, value in record.items() if key != "result"}
            self._db.execute("UPDATE jobs SET state=?, record=?, summary=? WHERE id=?", (
                "interrupted", json.dumps(record, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False), identifier,
            ))
        self._db.commit()

    @staticmethod
    def _validate_lane(lane):
        if lane not in LANES:
            raise PipelineError("INVALID_JOB_LANE", "任务队列只能是 document、image 或 audio", 400)

    def _ensure_open(self):
        if self._closed:
            raise PipelineError("SCHEDULER_CLOSED", "任务调度器已关闭", 503)

    def _persist(self, job):
        record = job._record()
        summary = {key: value for key, value in record.items() if key != "result"}
        self._db.execute("""INSERT INTO jobs(id,lane,state,created_at,record,summary) VALUES(?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET state=excluded.state,record=excluded.record,summary=excluded.summary""", (
            job.id, job.lane, job.state, job.created_at, json.dumps(record, ensure_ascii=False),
            json.dumps(summary, ensure_ascii=False),
        ))
        self._db.commit()
        if self._on_event is not None:
            self._events.append(record)

    def _emit_events(self):
        # Drain in persisted order without holding the job/database lock during
        # user callbacks. Reentrant callbacks can query, submit or cancel safely.
        if not self._event_lock.acquire(blocking=False):
            return
        while True:
            with self._lock:
                if not self._events:
                    self._event_lock.release()
                    return
                record = self._events.popleft()
            try:
                self._on_event(record)
            except Exception:
                # Observers cannot change a task's execution or persistence.
                pass

    def submit(self, lane, name, action: Callable, *, source="api", context=None,
               job_id=None, project_id=None):
        self._validate_lane(lane)
        identifier = job_id or uuid4().hex
        if not isinstance(identifier, str) or not identifier or len(identifier) > 128:
            raise PipelineError("INVALID_JOB_ID", "任务 ID 无效", 400)
        if not callable(action):
            raise TypeError("action must be callable")
        with self._lock:
            self._ensure_open()
            if self._closing:
                raise PipelineError("SCHEDULER_CLOSING", "后端正在关闭，不能提交新任务", 503)
            if self._db.execute("SELECT 1 FROM jobs WHERE id=?", (identifier,)).fetchone():
                raise PipelineError("DUPLICATE_JOB_ID", "此任务 ID 已存在，请查询原任务或使用新 ID", 409)
            job = Job(identifier, lane, str(name), source, context or ExecutionContext(source=source),
                      project_id=project_id, _scheduler=self)
            self._jobs[job.id] = job
            self._persist(job)
            try:
                job._worker_future = self._pools[lane].submit(self._execute, job, action)
            except Exception as error:
                job.state = "failed"
                job.error = {"code": "JOB_SUBMIT_FAILED", "message": redact(str(error)), "status_code": 503}
                job.finished_at = job.updated_at = _now()
                self._persist(job)
                job.future.set_exception(error)
                self._retire(job)
                raise
        self._emit_events()
        return job

    def run(self, lane, name, action, **kwargs):
        current = self.current_job()
        if current is not None:
            # Accidentally awaiting work on one's own serial executor would
            # deadlock. Nested service calls should use the current context.
            raise PipelineError("NESTED_JOB", "任务内部不能同步等待另一个队列任务", 409)
        return self.submit(lane, name, action, **kwargs).future.result()

    def _execute(self, job, action):
        result = None
        failure = None
        try:
            with self._lock:
                if job.state != "queued":
                    return
                if job.context.is_cancelled() or job.future.cancelled():
                    self._cancel_queued(job)
                    skip = True
                else:
                    skip = False
                    job.future.set_running_or_notify_cancel()
                    job.state = "running"
                    job.started_at = job.updated_at = _now()
                    self._persist(job)
            self._emit_events()
            if skip:
                return
            self._local.job = job
            try:
                result = action(job.context)
            except BaseException as error:
                failure = error
            with self._lock:
                if failure is not None:
                    job.state = "cancelled" if job.context.is_cancelled() else "failed"
                    job.error = {
                        "code": getattr(failure, "code", "JOB_FAILED"), "message": redact(str(failure)),
                        "status_code": getattr(failure, "status_code", 400 if isinstance(failure, ValueError) else 500),
                    }
                    if isinstance(failure, PipelineError) and failure.details is not None:
                        job.error["details"] = _wire(failure.details)
                else:
                    job.result = _wire(result)
                    status = result.get("status") if isinstance(result, dict) else None
                    job.state = {
                        "partial": "partial", "failed": "failed", "error": "failed",
                        "cancelled": "cancelled", "stopped": "cancelled",
                    }.get(status, "succeeded")
                    if job.context.is_cancelled() and job.state in ("succeeded", "partial"):
                        job.state = "cancelled"
                    if job.state == "failed":
                        job.error = {"code": "JOB_FAILED", "message": redact(str(result.get("message") or "任务未成功完成，请检查结果报告"))}
                job.finished_at = job.updated_at = _now()
                self._persist(job)
            self._emit_events()
        except BaseException as error:
            # Always settle the public future even if result serialization or
            # persistence fails; callers must not wait forever on a dead worker.
            failure = failure or error
            with self._lock:
                job.state = "failed"
                job.error = {"code": "JOB_PERSIST_FAILED", "message": redact(str(error))}
                job.finished_at = job.updated_at = _now()
                job.result = None
                try:
                    self._persist(job)
                except Exception:
                    # A broken database will be recovered as interrupted on
                    # restart; the live future still communicates the failure.
                    pass
            self._emit_events()
        finally:
            self._local.job = None
            if not job.future.done():
                if failure is not None:
                    job.future.set_exception(failure)
                else:
                    job.future.set_result(result)
            with self._lock:
                self._retire(job)

    def _retire(self, job):
        # Completed results live in SQLite. Keeping Future/result/model trees
        # for every job here would otherwise grow memory for the server's life.
        if job.state in TERMINAL_STATES and job.future.done():
            self._jobs.pop(job.id, None)

    def current_job(self):
        return getattr(self._local, "job", None)

    def get_future(self, job_id):
        """Return a waitable handle without tying up an HTTP worker thread."""
        with self._lock:
            self._ensure_open()
            if job_id in self._jobs:
                return self._jobs[job_id].future
            record = self.get(job_id)
        future = Future()
        state = record["state"]
        if state not in TERMINAL_STATES:
            raise PipelineError("JOB_NOT_LOCAL", "任务不属于当前后端进程，无法等待其执行", 409)
        if state == "interrupted" or (state in ("failed", "cancelled") and record["result"] is None):
            error = record.get("error") or {}
            future.set_exception(PipelineError(
                error.get("code", "JOB_FAILED"), error.get("message", "任务未完成"),
                409 if state in ("cancelled", "interrupted") else error.get("status_code", 500),
                details=error.get("details"),
            ))
        else:
            future.set_result(record["result"])
        return future

    async def wait(self, job_id):
        # A disconnected/cancelled HTTP waiter must not cancel the shared task
        # future. Only the explicit cancellation endpoint changes job state.
        return await asyncio.shield(asyncio.wrap_future(self.get_future(job_id)))

    def get(self, job_id):
        with self._lock:
            self._ensure_open()
            row = self._db.execute("SELECT record FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise PipelineError("JOB_NOT_FOUND", "任务不存在", 404)
            return json.loads(row[0])

    def list(self, lane=None, limit=100):
        if lane is not None:
            self._validate_lane(lane)
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            self._ensure_open()
            if lane is None:
                rows = self._db.execute("SELECT id,summary FROM jobs ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
            else:
                rows = self._db.execute("SELECT id,summary FROM jobs WHERE lane=? ORDER BY rowid DESC LIMIT ?", (lane, limit)).fetchall()
            results = []
            migrated = False
            for identifier, summary in rows:
                if summary is None:
                    # Only pre-summary schema rows need a one-time full read.
                    payload = self._db.execute("SELECT record FROM jobs WHERE id=?", (identifier,)).fetchone()[0]
                    record = json.loads(payload)
                    metadata = {key: value for key, value in record.items() if key != "result"}
                    summary = json.dumps(metadata, ensure_ascii=False)
                    self._db.execute("UPDATE jobs SET summary=? WHERE id=?", (summary, identifier))
                    migrated = True
                    results.append(metadata)
                else:
                    results.append(json.loads(summary))
            if migrated:
                self._db.commit()
            return results

    def lanes(self):
        with self._lock:
            result = {lane: {"running": None, "queued": []} for lane in LANES}
            for job in self._jobs.values():
                if job.state in TERMINAL_STATES:
                    continue
                record = job._record(include_result=False)
                if job.state == "queued":
                    result[job.lane]["queued"].append(record)
                else:
                    result[job.lane]["running"] = record
            return result

    def _cancel_queued(self, job):
        job.context.cancel()
        job.state = "cancelled"
        job.finished_at = job.updated_at = _now()
        job.error = {"code": "JOB_CANCELLED", "message": "任务在开始执行前已取消"}
        self._persist(job)
        if job._worker_future is not None:
            job._worker_future.cancel()
        if not job.future.done():
            job.future.set_exception(PipelineError("JOB_CANCELLED", job.error["message"], 409))
        self._retire(job)

    def cancel(self, job_id):
        with self._lock:
            self._ensure_open()
            job = self._jobs.get(job_id)
            if job is None:
                # Completed historical jobs are idempotent cancellation targets.
                return self.get(job_id)
            if job.state == "queued":
                self._cancel_queued(job)
            elif job.state in ("running", "cancelling"):
                job.context.cancel()
                if job.state != "cancelling":
                    job.state = "cancelling"
                    job.updated_at = _now()
                    self._persist(job)
            record = job._record()
        self._emit_events()
        return record

    def update_progress(self, job_id, progress):
        with self._lock:
            self._ensure_open()
            job = self._jobs.get(job_id)
            if job is None:
                raise PipelineError("JOB_NOT_FOUND", "任务不存在", 404)
            if job.state in TERMINAL_STATES:
                return
            job.progress = _wire(progress)
            job.updated_at = _now()
            self._persist(job)
        self._emit_events()

    def close(self):
        if self.current_job() is not None:
            raise PipelineError("CLOSE_FROM_JOB", "不能在正在执行的任务内部关闭调度器", 409)
        with self._lock:
            if self._closed:
                return
            wait_for_other_close = self._closing
            self._closing = True
            identifiers = [job.id for job in self._jobs.values() if job.state not in TERMINAL_STATES]
        if wait_for_other_close:
            self._close_done.wait()
            return
        try:
            for identifier in identifiers:
                self.cancel(identifier)
            for pool in self._pools.values():
                pool.shutdown(wait=True, cancel_futures=True)
        finally:
            with self._lock:
                self._db.close()
                self._closed = True
                self._close_done.set()
