from __future__ import annotations
import threading

# In-memory task state
_task_status: dict[str, dict] = {}
_cl_task_status: dict[str, dict] = {}
_fetch_status: dict = {"status": "idle", "message": ""}
_lock = threading.Lock()


def clear_task_state() -> None:
    with _lock:
        _task_status.clear()
        _cl_task_status.clear()


def get_task_status(job_id: str) -> dict:
    with _lock:
        return dict(_task_status.get(job_id, {"status": "idle", "pdf_path": None, "error": None, "stage": ""}))


def get_cl_task_status(job_id: str) -> dict:
    with _lock:
        return dict(_cl_task_status.get(job_id, {"status": "idle", "pdf_path": None, "error": None, "stage": ""}))


def get_fetch_status() -> dict:
    with _lock:
        return dict(_fetch_status)


def trigger_resume(job_id: str) -> None:
    from .documents import _build_resume
    with _lock:
        if _task_status.get(job_id, {}).get("status") == "building":
            return
        _task_status[job_id] = {"status": "building", "pdf_path": None, "error": None, "stage": "Starting…"}
    t = threading.Thread(target=_build_resume, args=(job_id,), daemon=True)
    t.start()


def trigger_cover_letter(job_id: str) -> None:
    from .documents import _build_cover_letter
    with _lock:
        if _cl_task_status.get(job_id, {}).get("status") == "building":
            return
        _cl_task_status[job_id] = {"status": "building", "pdf_path": None, "error": None, "stage": "Starting…"}
    t = threading.Thread(target=_build_cover_letter, args=(job_id,), daemon=True)
    t.start()


def trigger_fetch() -> None:
    from .fetch_worker import _run_fetch
    with _lock:
        if _fetch_status.get("status") == "running":
            return
        _fetch_status["status"] = "running"
        _fetch_status["message"] = "Starting…"
    t = threading.Thread(target=_run_fetch, daemon=True)
    t.start()


def _set_stage(job_id: str, stage: str) -> None:
    with _lock:
        if job_id in _task_status:
            _task_status[job_id]["stage"] = stage


def _set_cl_stage(job_id: str, stage: str) -> None:
    with _lock:
        if job_id in _cl_task_status:
            _cl_task_status[job_id]["stage"] = stage
