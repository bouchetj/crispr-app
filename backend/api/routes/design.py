import hashlib
import json
import logging

from fastapi import APIRouter, HTTPException

from schemas.design import DesignRequest, DesignResponse
from services.sequence import sanitize
from store.jobs import JobStoreUnavailable, create_job, find_cached_job, update_job
from backend.tasks.design import run_design_job

router = APIRouter()
logger = logging.getLogger(__name__)


def _design_input_hash(req: DesignRequest, sanitized_sequence: str) -> str:
    """Create a hash of the design input to use for caching."""
    payload = {
        "sequence": sanitized_sequence,
        "nuclease": req.nuclease,
        "pam": req.pam,
        "genome": req.genome,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@router.post("/design", response_model=DesignResponse)
def design_guides(req: DesignRequest):
    """Submit a guide RNA design job."""
    
    if req.nuclease != "SpCas9" or req.pam != "NGG" or req.genome != "hg38":
        raise HTTPException(status_code=400, detail="Only SpCas9 NGG design on hg38 is currently supported")

    seq = sanitize(req.sequence)
    if not seq:
        raise HTTPException(status_code=400, detail="Sequence is empty after sanitization")

    cache_key = _design_input_hash(req, seq)

    try:
        cached_job = find_cached_job(cache_key)
    except JobStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if cached_job and cached_job.get("payload"):
        payload = cached_job["payload"]
        return DesignResponse(
            job_id=cached_job["job_id"],
            status=cached_job["status"],
            message=cached_job.get("message"),
            num_candidates=payload.get("num_candidates"),
            guides=payload.get("guides"),
        )

    try:
        job_id = create_job(
            status="queued",
            message="Design job queued",
            progress=0.0,
            stage="queued",
            details={"total_guides": None, "completed_guides": 0},
            input_hash=cache_key,
            request_payload=req.model_dump(),
        )
    except JobStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        run_design_job.apply_async(
            kwargs={"job_id": job_id, "sequence": seq, "request_payload": req.model_dump()}
        )
    except Exception as exc:
        logger.exception("Failed to enqueue design job %s", job_id)
        failure_message = "Failed to enqueue design job"
        try:
            update_job(
                job_id,
                status="failed",
                stage="error",
                message=failure_message,
                progress=1.0,
            )
        except JobStoreUnavailable:
            logger.error("Unable to mark job %s as failed because job store is unavailable", job_id)
        raise HTTPException(status_code=503, detail="Unable to enqueue design job") from exc

    return DesignResponse(job_id=job_id, status="queued", message="Design job queued")
