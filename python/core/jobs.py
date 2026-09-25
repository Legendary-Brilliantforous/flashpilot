"""Isolated FlashJob lifecycle (Phase 1 job layer).

Every device operation belongs to exactly one :class:`FlashJob`:

    job_id, device_key, job/mode/method, validated action ids,
    state machine, per-job cancel event, per-job log buffer,
    error detail, timestamps.

States mirror the universal flash state machine: CREATED → VALIDATED →
RUNNING → COMPLETED, with failure terminals CANCELLED / TIMEOUT / FAILED
(and DISCONNECTED folded into FAILED with the transport error preserved —
the monitor owns reconnect; the job owns the attempt).

Cancellation: :meth:`JobManager.cancel_job` / :meth:`cancel_device` trip
the shared cooperative registry (``core/cancel.py``) for the job's device
scope AND mark the job, so flow checks and the bridge poll loop observe
the same stop. One-op-per-device is still enforced by the GUI run guard,
so tripping a device scope today affects exactly that device's job; the
per-job event exists for direct checks as runners adopt them.
"""

import threading
import time
import uuid

# Terminal + active state sets (universal flash state machine vocabulary).
ACTIVE_STATES = ("CREATED", "VALIDATED", "RUNNING")
TERMINAL_STATES = ("COMPLETED", "CANCELLED", "TIMEOUT", "FAILED")

# Keep bounded history so long sessions cannot grow memory without limit.
MAX_FINISHED_JOBS = 50


class FlashJob:
    """One isolated device operation."""

    def __init__(self, device_key, job, mode, method, action_ids=()):
        self.job_id = uuid.uuid4().hex[:12]
        self.device_key = device_key
        self.job = job
        self.mode = mode
        self.method = method
        self.action_ids = list(action_ids or [])
        self.state = "CREATED"
        self.error = ""
        self.error_code = ""
        self.created = time.monotonic()
        self.started = 0.0
        self.finished = 0.0
        self.logs = []
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_active(self):
        with self._lock:
            return self.state in ACTIVE_STATES

    def set_state(self, state, error="", error_code=""):
        with self._lock:
            if self.state in TERMINAL_STATES:
                return False
            self.state = state
            if error:
                self.error = str(error)
            if error_code:
                self.error_code = str(error_code)
            now = time.monotonic()
            if state == "RUNNING" and not self.started:
                self.started = now
            if state in TERMINAL_STATES:
                self.finished = now
            return True

    def append_log(self, line):
        with self._lock:
            if len(self.logs) < 5000:
                self.logs.append(line)

    def request_cancel(self):
        self._cancel.set()

    @property
    def cancel_requested(self):
        return self._cancel.is_set()

    def duration(self):
        end = self.finished or time.monotonic()
        start = self.started or self.created
        return max(0.0, end - start)

    def summary(self):
        with self._lock:
            return {
                "job_id": self.job_id,
                "device_key": self.device_key,
                "job": self.job,
                "mode": self.mode,
                "method": self.method,
                "action_ids": list(self.action_ids),
                "state": self.state,
                "error": self.error,
                "error_code": self.error_code,
                "duration_s": round(self.duration(), 1),
                "log_lines": len(self.logs),
            }


def classify_failure(exc, device_key=None):
    """Map an exception to (state, code): cancellation, timeout, or failure.

    Order matters: cancelled-during-timeout must read CANCELLED, so the
    cancel registries are consulted first — scoped to ``device_key`` (a
    timeout on one phone must not read CANCELLED because another phone's
    scope was tripped).
    """
    from . import cancel as _cancel

    name = type(exc).__name__
    text = str(exc)
    if _is_cancel_exc(exc):
        return "CANCELLED", getattr(exc, "code", "") or "CANCELLED"
    if _cancel.cancel_requested(key=device_key):
        return "CANCELLED", "CANCELLED"
    if "timeout" in name.lower() or "timeout" in text.lower():
        return "TIMEOUT", getattr(exc, "code", "") or "TIMEOUT"
    return "FAILED", getattr(exc, "code", "") or "FAILED"


def _is_cancel_exc(exc):
    """True for the flow/bridge cancellation exception types (duck-typed so
    this module never imports GUI-adjacent flow machinery at module load)."""
    return isinstance(exc, RuntimeError) and type(exc).__name__ in (
        "FlowCancelled",
        "BridgeCancelled",
    )


class JobManager:
    """Thread-safe job registry. One module-global instance is exposed via
    the module-level functions below (GUI runners share it)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jobs = {}

    def start_job(self, device_key, job, mode, method, action_ids=()):
        j = FlashJob(device_key, job, mode, method, action_ids)
        with self._lock:
            self._jobs[j.job_id] = j
        return j

    def get_job(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    def active_jobs(self, device_key=None):
        with self._lock:
            jobs = [j for j in self._jobs.values() if j.is_active]
        if device_key is not None:
            jobs = [j for j in jobs if j.device_key == device_key]
        return jobs

    def finish_job(self, job_id, state, error="", error_code=""):
        with self._lock:
            j = self._jobs.get(job_id)
        if j is None:
            return False
        ok = j.set_state(state, error, error_code)
        self._prune()
        return ok

    def cancel_job(self, job_id):
        """Mark one job cancelled and trip its device scope in the shared
        cooperative registry (flow checks + bridge poll loop observe it)."""
        from . import cancel as _cancel

        with self._lock:
            j = self._jobs.get(job_id)
        if j is None or not j.is_active:
            return False
        j.request_cancel()
        _cancel.request_cancel(j.device_key)
        j.set_state("CANCELLED", "cancelled by user", "CANCELLED")
        return True

    def cancel_device(self, device_key):
        """Cancel every active job on one device; other devices keep running."""
        cancelled = []
        for j in self.active_jobs(device_key):
            if self.cancel_job(j.job_id):
                cancelled.append(j.job_id)
        return cancelled

    def _prune(self):
        with self._lock:
            done = [j for j in self._jobs.values() if not j.is_active]
            if len(done) > MAX_FINISHED_JOBS:
                done.sort(key=lambda j: j.finished or 0.0)
                for j in done[: len(done) - MAX_FINISHED_JOBS]:
                    del self._jobs[j.job_id]

    def reset(self):
        """Test hook: drop all jobs."""
        with self._lock:
            self._jobs.clear()


_manager = JobManager()


def start_job(device_key, job, mode, method, action_ids=()):
    return _manager.start_job(device_key, job, mode, method, action_ids)


def get_job(job_id):
    return _manager.get_job(job_id)


def active_jobs(device_key=None):
    return _manager.active_jobs(device_key)


def finish_job(job_id, state, error="", error_code=""):
    return _manager.finish_job(job_id, state, error, error_code)


def cancel_job(job_id):
    return _manager.cancel_job(job_id)


def cancel_device(device_key):
    return _manager.cancel_device(device_key)
