from typing import List

from fastapi import APIRouter, HTTPException
from schemas.design import JobStatus
from store.jobs import JobStoreUnavailable, get_job, list_jobs

router = APIRouter()

@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str):
    """Get the status of a job by its ID."""
    try:
        job = get_job(job_id)
    except JobStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        message=job.get("message"),
        stage=job.get("stage"),
        progress=job.get("progress"),
        details=job.get("details"),
        result=job.get("payload"),
        created_at=job.get("created_at"),
        updated_at=job.get("updated_at"),
    )


@router.get("/jobs", response_model=List[JobStatus])
def list_recent_jobs(limit: int = 20, offset: int = 0):
    """List recent jobs."""
    try:
        records = list_jobs(limit=limit, offset=offset)
    except JobStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result: List[JobStatus] = []
    for job in records:
        result.append(
            JobStatus(
                job_id=job["job_id"],
                status=job["status"],
                message=job.get("message"),
                stage=job.get("stage"),
                progress=job.get("progress"),
                details=job.get("details"),
                result=job.get("payload"),
                created_at=job.get("created_at"),
                updated_at=job.get("updated_at"),
            )
        )

    return result
