import pytest

from api.routes import design as design_route


def test_design_route_apply_async_failure(client, monkeypatch: pytest.MonkeyPatch):
    created_jobs = []
    updates = []

    def fake_create_job(**kwargs):
        created_jobs.append(kwargs)
        return "job-apply-fail"

    def fake_update_job(job_id, **kwargs):
        updates.append((job_id, kwargs))
        return True

    def fake_apply_async(*, kwargs=None):
        raise RuntimeError("queue down")

    monkeypatch.setattr(design_route, "create_job", fake_create_job)
    monkeypatch.setattr(design_route, "update_job", fake_update_job)
    monkeypatch.setattr(design_route, "find_cached_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(design_route.run_design_job, "apply_async", fake_apply_async)

    payload = {
        "sequence": "GAGTCCGAGCAGAAGAAGAAGGG",
        "nuclease": "SpCas9",
        "pam": "NGG",
        "genome": "hg38",
    }

    response = client.post("/api/design", json=payload)
    assert response.status_code == 503
    assert response.json()["detail"] == "Unable to enqueue design job"

    assert created_jobs, "create_job should have been invoked"
    assert updates, "update_job should have been invoked on failure"

    job_id, final_update = updates[-1]
    assert job_id == "job-apply-fail"
    assert final_update["status"] == "failed"
    assert final_update["stage"] == "error"
    assert final_update["message"] == "Failed to enqueue design job"
    assert final_update["progress"] == 1.0


def test_design_route_returns_cached_job(client, monkeypatch: pytest.MonkeyPatch):
    cached_payload = {
        "num_candidates": 2,
        "guides": [],
    }

    cached_job = {
        "job_id": "job-cached",
        "status": "succeeded",
        "message": "Cached result",
        "payload": cached_payload,
    }

    monkeypatch.setattr(design_route, "find_cached_job", lambda *args, **kwargs: cached_job)

    def fail_create_job(**kwargs):
        raise AssertionError("create_job should not be invoked when cached job exists")

    monkeypatch.setattr(design_route, "create_job", fail_create_job)
    monkeypatch.setattr(design_route.run_design_job, "apply_async", lambda **kwargs: None)

    payload = {
        "sequence": "GAGTCCGAGCAGAAGAAGAAGGG",
        "nuclease": "SpCas9",
        "pam": "NGG",
        "genome": "hg38",
    }

    response = client.post("/api/design", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-cached"
    assert body["status"] == "succeeded"
    assert body["num_candidates"] == 2
    assert body["guides"] == []
