import copy
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from core.config import settings

from redis import Redis
from redis.exceptions import RedisError


class JobStoreUnavailable(RuntimeError):
    """Raised when the Redis-backed job store cannot be reached."""


_REDIS_CLIENT: Optional[Redis] = None

_JOB_INDEX_KEY = "jobs:index"
_JOB_INPUT_HASH_KEY = "jobs:input-hash"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_progress(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(1.0, value))


def _job_key(job_id: str) -> str:
    return f"jobs:{job_id}"


def _ensure_redis() -> Redis:
    global _REDIS_CLIENT

    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    url = settings.JOBS_REDIS_URL
    if not url:
        raise JobStoreUnavailable("JOBS_REDIS_URL is not configured")

    try:
        client = Redis.from_url(url, decode_responses=True)
        client.ping()
    except RedisError as exc:
        raise JobStoreUnavailable("Unable to connect to Redis job store") from exc

    _REDIS_CLIENT = client
    return client


def _serialize_job(job: Dict[str, Any]) -> str:
    payload = copy.deepcopy(job)
    for key in ("created_at", "updated_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return json.dumps(payload)


def _deserialize_job(raw: str) -> Dict[str, Any]:
    data = json.loads(raw)
    for key in ("created_at", "updated_at"):
        value = data.get(key)
        if isinstance(value, str):
            data[key] = datetime.fromisoformat(value)
    return data


def _record_job_index(client: Redis, job_id: str, score_time: datetime) -> None:
    client.zadd(_JOB_INDEX_KEY, {job_id: score_time.timestamp()})


def _sync_cache_mapping(
    client: Redis,
    *,
    job_id: str,
    job: Dict[str, Any],
    previous_input_hash: Optional[str],
    previous_cached: bool,
) -> None:
    current_hash = job.get("input_hash")
    is_cached = bool(job.get("cached")) and job.get("status") == "succeeded"

    if is_cached and current_hash:
        client.hset(_JOB_INPUT_HASH_KEY, current_hash, job_id)
    elif previous_cached and previous_input_hash:
        client.hdel(_JOB_INPUT_HASH_KEY, previous_input_hash)


def create_job(
    *,
    status: Literal["queued", "running", "succeeded", "failed"] = "queued",
    message: Optional[str] = None,
    progress: Optional[float] = None,
    stage: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    payload: Optional[Any] = None,
    input_hash: Optional[str] = None,
    request_payload: Optional[Any] = None,
) -> str:
    """Create a job entry and return its identifier."""

    job_id = str(uuid.uuid4())
    now = _utcnow()
    job_data: Dict[str, Any] = {
        "status": status,
        "message": message,
        "progress": _normalize_progress(progress),
        "stage": stage,
        "details": copy.deepcopy(details),
        "payload": copy.deepcopy(payload),
        "cached": False,
        "input_hash": input_hash,
        "request_payload": copy.deepcopy(request_payload),
        "created_at": now,
        "updated_at": now,
    }

    client = _ensure_redis()
    client.set(_job_key(job_id), _serialize_job(job_data))
    _record_job_index(client, job_id, now)
    _sync_cache_mapping(
        client,
        job_id=job_id,
        job=job_data,
        previous_input_hash=None,
        previous_cached=False,
    )

    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a job by its ID, or None if not found."""
    client = _ensure_redis()
    raw = client.get(_job_key(job_id))
    if raw is None:
        return None
    job = _deserialize_job(raw)
    return copy.deepcopy(job)


def update_job(
    job_id: str,
    *,
    status: Optional[Literal["queued", "running", "succeeded", "failed"]] = None,
    message: Optional[str] = None,
    progress: Optional[float] = None,
    stage: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    payload: Optional[Any] = None,
    input_hash: Optional[str] = None,
    request_payload: Optional[Any] = None,
    cached: Optional[bool] = None,
) -> bool:
    """Update fields of an existing job. Returns True if the job existed and was updated."""
    client = _ensure_redis()
    key = _job_key(job_id)
    raw = client.get(key)
    if raw is None:
        return False
    job = _deserialize_job(raw)

    previous_input_hash = job.get("input_hash")
    previous_cached = bool(job.get("cached"))

    if status is not None:
        job["status"] = status
    if message is not None:
        job["message"] = message
    if progress is not None:
        job["progress"] = _normalize_progress(progress)
    if stage is not None:
        job["stage"] = stage
    if details is not None:
        job["details"] = copy.deepcopy(details)
    if payload is not None:
        job["payload"] = copy.deepcopy(payload)
    if request_payload is not None:
        job["request_payload"] = copy.deepcopy(request_payload)
    if input_hash is not None:
        job["input_hash"] = input_hash
    if cached is not None:
        job["cached"] = cached

    if job.get("input_hash") and job.get("status") == "succeeded" and cached is None:
        job["cached"] = True
    elif "cached" not in job:
        job["cached"] = previous_cached

    job["updated_at"] = _utcnow()

    client = _ensure_redis()
    client.set(_job_key(job_id), _serialize_job(job))
    _record_job_index(client, job_id, job["updated_at"])
    _sync_cache_mapping(
        client,
        job_id=job_id,
        job=job,
        previous_input_hash=previous_input_hash,
        previous_cached=previous_cached,
    )
    return True


def reset_jobs() -> None:
    """Utility for tests: clear job storage."""

    client = _ensure_redis()
    keys = client.keys("jobs:*")
    if keys:
        client.delete(*keys)
    client.delete(_JOB_INDEX_KEY, _JOB_INPUT_HASH_KEY)


def list_jobs(*, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """List jobs in reverse chronological order."""
    client = _ensure_redis()
    if limit <= 0:
        return []

    start = max(offset, 0)
    end = start + limit - 1
    job_ids = client.zrevrange(_JOB_INDEX_KEY, start, end)
    results: List[Dict[str, Any]] = []

    for job_id in job_ids:
        raw = client.get(_job_key(job_id))
        if raw is None:
            client.zrem(_JOB_INDEX_KEY, job_id)
            continue
        job = _deserialize_job(raw)
        record = copy.deepcopy(job)
        record["job_id"] = job_id
        results.append(record)

    return results


def find_cached_job(input_hash: str) -> Optional[Dict[str, Any]]:
    """Find a previously completed job by its input hash, or None if not found."""
    client = _ensure_redis()
    job_id = client.hget(_JOB_INPUT_HASH_KEY, input_hash)
    if not job_id:
        return None

    raw = client.get(_job_key(job_id))
    if raw is None:
        client.hdel(_JOB_INPUT_HASH_KEY, input_hash)
        return None

    job = _deserialize_job(raw)
    if job.get("status") != "succeeded":
        client.hdel(_JOB_INPUT_HASH_KEY, input_hash)
        return None

    record = copy.deepcopy(job)
    record["job_id"] = job_id
    return record
