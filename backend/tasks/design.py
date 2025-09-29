from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from celery.utils.log import get_task_logger

from backend.celery_app.celery_app import celery_app
from core.config import settings
from services.design import design
from store.jobs import JobStoreUnavailable, update_job

logger = get_task_logger(__name__)


class JobUpdateError(RuntimeError):
    """Raised when a job state change cannot be persisted."""


@celery_app.task(bind=True, name="backend.tasks.design.run_design_job")
def run_design_job(self, job_id: str, sequence: str, request_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute CRISPR guide design asynchronously and persist status updates."""

    job_results_dir = Path(settings.CRISPRITZ_RESULTS_DIR) / job_id
    base_details: Dict[str, Any] = {
        "total_guides": None,
        "completed_guides": 0,
        "crispritz_results_dir": str(job_results_dir),
    }

    def persist_update(*, expect_existing: bool = True, **kwargs) -> None:
        try:
            updated = update_job(job_id, **kwargs)
        except JobStoreUnavailable as exc:
            raise JobUpdateError("Job store is unavailable") from exc
        if expect_existing and not updated:
            raise JobUpdateError(f"Job {job_id} no longer exists")

    def progress_callback(*, stage: str, message: str, progress=None, details=None):
        if details:
            base_details.update(details)
        current_details = dict(base_details)
        persist_update(
            status="running",
            stage=stage,
            message=message,
            progress=progress,
            details=current_details,
        )
        if progress is not None:
            self.update_state(state="PROGRESS", meta={"stage": stage, "progress": progress})

    try:
        persist_update(
            status="running",
            stage="starting",
            message="Initializing design workflow",
            progress=0.01,
            details=dict(base_details),
        )

        # Run design
        guides = design(
            sequence=sequence,
            nuclease=request_payload["nuclease"],
            pam=request_payload["pam"],
            genome=request_payload["genome"],
            progress_callback=progress_callback,
            crispritz_results_dir=job_results_dir,
        )

        base_details.update({"total_guides": len(guides), "completed_guides": len(guides)})
        payload = {
            "guides": [guide.model_dump() for guide in guides],
            "num_candidates": len(guides),
            "crispritz_results_dir": str(job_results_dir),
        }
        persist_update(
            status="succeeded",
            stage="completed",
            message=f"Design job completed with {len(guides)} guides",
            progress=1.0,
            details=dict(base_details),
            payload=payload,
        )
        return payload
    except JobUpdateError as exc:
        logger.error("Failed to persist job %s update: %s", job_id, exc)
        self.update_state(state="FAILURE", meta={"message": str(exc)})
        raise
    except Exception as exc: 
        logger.exception("Design job %s failed", job_id)
        try:
            persist_update(
                expect_existing=False,
                status="failed",
                stage="error",
                message=str(exc),
                progress=1.0,
                details=dict(base_details),
            )
        except JobUpdateError as update_exc:
            logger.error(
                "Unable to record failure for job %s due to job store error: %s",
                job_id,
                update_exc,
            )
        self.update_state(state="FAILURE", meta={"message": str(exc)})
        raise
