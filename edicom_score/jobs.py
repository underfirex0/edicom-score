"""Tiny in-process job runner for long operations (imports, ZIP batches). One worker thread per job."""
from __future__ import annotations
import threading, time, uuid, traceback
from dataclasses import dataclass, field
from typing import Any, Callable

@dataclass
class Job:
    id: str; kind: str; total: int = 1; step: int = 0; label: str = "En attente"
    status: str = "running"; result: Any = None; error: str | None = None
    started: float = field(default_factory=time.time); finished: float | None = None
    def update(self, step: int, label: str | None = None):
        self.step = step
        if label: self.label = label
    def to_dict(self):
        end = self.finished or time.time()
        return {"id": self.id, "kind": self.kind, "status": self.status, "step": self.step, "total": self.total, "label": self.label,
                "progress": min(1.0, self.step / self.total) if self.total else 1.0, "result": self.result, "error": self.error, "seconds": round(end - self.started, 1)}

_JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()

def start(kind: str, fn: Callable[[Job], Any], total: int = 1) -> Job:
    job = Job(uuid.uuid4().hex[:12], kind, total)
    with _LOCK:
        _JOBS[job.id] = job
        for k in [k for k, j in _JOBS.items() if j.finished and time.time() - j.finished > 3600]: _JOBS.pop(k, None)
    def run():
        try:
            job.result = fn(job); job.step = job.total; job.status = "done"
        except Exception as e:                                   # surfaced to the UI, never swallowed
            job.error = str(e) or type(e).__name__; job.status = "error"; job.trace = traceback.format_exc()
        finally:
            job.finished = time.time()
    threading.Thread(target=run, daemon=True).start()
    return job

def get(job_id: str) -> Job | None:
    return _JOBS.get(job_id)
