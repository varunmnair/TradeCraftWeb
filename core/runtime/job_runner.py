"""Background job runner for asynchronous workflows."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from core.runtime.session_registry import SessionRegistry
from db import models
from db.database import SessionLocal

LOGGER = logging.getLogger(__name__)


class JobExecutionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = "job_failed",
        context: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}
        self.retryable = retryable


class JobRunner:
    def __init__(
        self,
        session_factory=SessionLocal,
        session_registry: SessionRegistry | None = None,
        max_workers: int = 4,
    ) -> None:
        self._session_factory = session_factory
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._session_registry = session_registry

    def register_handler(
        self, job_type: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        self._handlers[job_type] = handler

    def start_job(
        self, *, session_id: str, job_type: str, payload: Dict[str, Any]
    ) -> int:
        if job_type not in self._handlers:
            raise ValueError(f"Handler for job_type {job_type} is not registered")

        payload = {**payload, "session_id": session_id}
        payload_json = json.dumps(payload)

        user_id = None
        if self._session_registry:
            context = self._session_registry.get_session(session_id)
            if context:
                user_id = context.user_record_id

        with self._session_factory() as db:
            job = models.Job(
                user_id=user_id,
                session_id=session_id,
                job_type=job_type,
                status="pending",
                progress=0.0,
                payload_json=payload_json,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id

        self._executor.submit(self._execute_job, job_id)
        return job_id

    def get_job(self, job_id: int) -> Dict[str, Any]:
        with self._session_factory() as db:
            job = db.get(models.Job, job_id)
            if not job:
                raise ValueError("Job not found")
            return self._serialize_job(job)

    def list_jobs(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._session_factory() as db:
            query = db.query(models.Job)
            if session_id:
                query = query.filter(models.Job.session_id == session_id)
            jobs = query.order_by(models.Job.created_at.desc()).all()
            return [self._serialize_job(job) for job in jobs]

    def get_latest_result(
        self, *, session_id: str, job_type: str
    ) -> Optional[Dict[str, Any]]:
        with self._session_factory() as db:
            query = db.query(models.Job).filter(
                models.Job.session_id == session_id,
                models.Job.job_type == job_type,
                models.Job.status == "succeeded",
            )
            job = query.order_by(models.Job.updated_at.desc()).first()
            if not job or not job.result_json:
                return None
            return json.loads(job.result_json)

    def _execute_job(self, job_id: int) -> None:
        db: Session = self._session_factory()
        try:
            job = db.get(models.Job, job_id)
            if not job:
                return
            job.status = "running"
            job.progress = 0.1
            job.updated_at = datetime.now(timezone.utc)
            db.commit()

            payload = json.loads(job.payload_json or "{}")
            handler = self._handlers[job.job_type]
            try:
                result = handler(payload)
                job.status = "succeeded"
                job.progress = 1.0
                job.result_json = json.dumps(result)
                job.error_json = None
            except JobExecutionError as err:
                LOGGER.exception("Job %s failed: %s", job_id, err)
                job.status = "failed"
                job.error_json = json.dumps(
                    {
                        "error_code": err.error_code,
                        "message": str(err),
                        "context": err.context,
                        "retryable": err.retryable,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Job %s encountered an unexpected error", job_id)
                job.status = "failed"
                job.error_json = json.dumps(
                    {
                        "error_code": "internal_error",
                        "message": str(exc),
                        "context": {},
                        "retryable": False,
                    }
                )
            finally:
                job.updated_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()

    @staticmethod
    def _serialize_job(job: models.Job) -> Dict[str, Any]:
        return {
            "id": job.id,
            "user_id": job.user_id,
            "session_id": job.session_id,
            "job_type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "result": json.loads(job.result_json) if job.result_json else None,
            "error": json.loads(job.error_json) if job.error_json else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }

    def get_job_failures(self, job_id: int) -> Dict[str, Any]:
        with self._session_factory() as db:
            job = db.get(models.Job, job_id)
            if not job:
                raise ValueError("Job not found")

            result = json.loads(job.result_json) if job.result_json else {}
            failures = result.get("failures", [])

            return {
                "job_id": job_id,
                "job_type": job.job_type,
                "operation": result.get("operation"),
                "total": result.get("total", 0),
                "succeeded": result.get("succeeded", 0),
                "failed": result.get("failed", 0),
                "failures": failures,
            }
