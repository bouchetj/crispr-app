from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from api.routes import jobs as jobs_route
from store.jobs import JobStoreUnavailable


def test_get_job_status_success(monkeypatch: pytest.MonkeyPatch):
    now = datetime.now(timezone.utc)
    job_record = {
        "status": "succeeded",
        "message": "done",
        "stage": "completed",
        "progress": 1.0,
        "details": {"foo": "bar"},
        "payload": {"guides": []},
        "created_at": now,
        "updated_at": now,
    }

    def fake_get_job(job_id: str):
        assert job_id == "abc"
        return job_record

    monkeypatch.setattr(jobs_route, "get_job", fake_get_job)

    resp = jobs_route.get_job_status("abc")
    assert resp.job_id == "abc"
    assert resp.status == "succeeded"
    assert resp.details == {"foo": "bar"}
    assert resp.result == {"guides": []}
    assert resp.created_at == now
    assert resp.updated_at == now


def test_get_job_status_handles_store_errors(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(jobs_route, "get_job", lambda job_id: (_ for _ in ()).throw(JobStoreUnavailable("down")))
    with pytest.raises(HTTPException) as excinfo:
        jobs_route.get_job_status("abc")
    assert excinfo.value.status_code == 503
    assert "down" in excinfo.value.detail


def test_get_job_status_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(jobs_route, "get_job", lambda job_id: None)
    with pytest.raises(HTTPException) as excinfo:
        jobs_route.get_job_status("zzz")
    assert excinfo.value.status_code == 404
    assert "Job not found" in excinfo.value.detail


def test_list_recent_jobs_success(monkeypatch: pytest.MonkeyPatch):
    now = datetime.utcnow()
    records = [
        {
            "job_id": "b",
            "status": "succeeded",
            "message": "done",
            "stage": "complete",
            "progress": 1.0,
            "details": {"foo": "bar"},
            "payload": {"guides": []},
            "created_at": now,
            "updated_at": now,
        },
        {
            "job_id": "a",
            "status": "queued",
            "message": "queued",
            "stage": "queued",
            "progress": 0.0,
            "details": None,
            "payload": None,
            "created_at": now,
            "updated_at": now,
        },
    ]

    monkeypatch.setattr(jobs_route, "list_jobs", lambda limit, offset: records)

    result = jobs_route.list_recent_jobs(limit=10, offset=0)
    assert len(result) == 2
    assert result[0].job_id == "b"
    assert result[1].status == "queued"


def test_list_recent_jobs_handles_store_errors(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(jobs_route, "list_jobs", lambda limit, offset: (_ for _ in ()).throw(JobStoreUnavailable("down")))
    with pytest.raises(HTTPException) as excinfo:
        jobs_route.list_recent_jobs()
    assert excinfo.value.status_code == 503
    assert "down" in excinfo.value.detail
