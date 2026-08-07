from __future__ import annotations
import threading

from .user_context import get_current_user_id, user_context

# In-memory task state, keyed by user_id then job_id / fetch
_task_status: dict[str, dict[str, dict]] = {}
_cl_task_status: dict[str, dict[str, dict]] = {}
_fetch_status: dict[str, dict] = {}
_lock = threading.Lock()

_IDLE_FETCH = {"status": "idle", "message": ""}
_IDLE_JOB = {"status": "idle", "pdf_path": None, "error": None, "stage": ""}


def _job_map(store: dict[str, dict[str, dict]], user_id: str) -> dict[str, dict]:
    if user_id not in store:
        store[user_id] = {}
    return store[user_id]


def clear_task_state(user_id: str | None = None) -> None:
    uid = user_id or get_current_user_id()
    with _lock:
        _task_status.pop(uid, None)
        _cl_task_status.pop(uid, None)
        _fetch_status[uid] = dict(_IDLE_FETCH)


def get_task_status(job_id: str, user_id: str | None = None) -> dict:
    uid = user_id or get_current_user_id()
    with _lock:
        return dict(_job_map(_task_status, uid).get(job_id, _IDLE_JOB))


def get_cl_task_status(job_id: str, user_id: str | None = None) -> dict:
    uid = user_id or get_current_user_id()
    with _lock:
        return dict(_job_map(_cl_task_status, uid).get(job_id, _IDLE_JOB))


def get_fetch_status(user_id: str | None = None) -> dict:
    uid = user_id or get_current_user_id()
    with _lock:
        return dict(_fetch_status.get(uid, _IDLE_FETCH))


def trigger_resume(job_id: str, user_id: str | None = None) -> None:
    from .documents import _build_resume
    uid = user_id or get_current_user_id()
    with _lock:
        m = _job_map(_task_status, uid)
        if m.get(job_id, {}).get("status") == "building":
            return
        m[job_id] = {"status": "building", "pdf_path": None, "error": None, "stage": "Starting…"}

    def run():
        with user_context(uid):
            _build_resume(job_id)

    threading.Thread(target=run, daemon=True).start()


def trigger_cover_letter(job_id: str, user_id: str | None = None) -> None:
    from .documents import _build_cover_letter
    uid = user_id or get_current_user_id()
    with _lock:
        m = _job_map(_cl_task_status, uid)
        if m.get(job_id, {}).get("status") == "building":
            return
        m[job_id] = {"status": "building", "pdf_path": None, "error": None, "stage": "Starting…"}

    def run():
        with user_context(uid):
            _build_cover_letter(job_id)

    threading.Thread(target=run, daemon=True).start()


def trigger_fetch(user_id: str | None = None) -> bool:
    """Start the fetch thread. Returns True if started, False if already running."""
    from .fetch_worker import _run_fetch
    uid = user_id or get_current_user_id()
    with _lock:
        cur = _fetch_status.get(uid, _IDLE_FETCH)
        if cur.get("status") == "running":
            return False
        _fetch_status[uid] = {"status": "running", "message": "Starting…"}

    def run():
        with user_context(uid):
            _run_fetch()

    threading.Thread(target=run, daemon=True).start()
    return True


def _set_stage(job_id: str, stage: str, user_id: str | None = None) -> None:
    uid = user_id or get_current_user_id()
    with _lock:
        m = _job_map(_task_status, uid)
        if job_id in m:
            m[job_id]["stage"] = stage


def _set_cl_stage(job_id: str, stage: str, user_id: str | None = None) -> None:
    uid = user_id or get_current_user_id()
    with _lock:
        m = _job_map(_cl_task_status, uid)
        if job_id in m:
            m[job_id]["stage"] = stage


def _set_cl_preview(job_id: str, preview: str, user_id: str | None = None) -> None:
    """Store a live prose preview of the cover letter as it streams in."""
    uid = user_id or get_current_user_id()
    with _lock:
        m = _job_map(_cl_task_status, uid)
        if job_id in m:
            m[job_id]["preview"] = preview


def set_job_result(job_id: str, entry: dict, *, is_resume: bool, user_id: str | None = None) -> None:
    uid = user_id or get_current_user_id()
    store = _task_status if is_resume else _cl_task_status
    with _lock:
        _job_map(store, uid)[job_id] = entry


def set_fetch_message(message: str, user_id: str | None = None) -> None:
    uid = user_id or get_current_user_id()
    with _lock:
        cur = _fetch_status.setdefault(uid, dict(_IDLE_FETCH))
        cur["message"] = message


def set_fetch_done(message: str, user_id: str | None = None) -> None:
    uid = user_id or get_current_user_id()
    with _lock:
        _fetch_status[uid] = {"status": "done", "message": message}


def set_fetch_error(message: str, user_id: str | None = None) -> None:
    uid = user_id or get_current_user_id()
    with _lock:
        _fetch_status[uid] = {"status": "error", "message": message}
