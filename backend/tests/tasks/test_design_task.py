import sys
import types
import importlib

from pathlib import Path

import pytest

from core.config import settings

# Celery stub 
if "celery" not in sys.modules:
    celery_stub = types.ModuleType("celery")

    class DummyConf(dict):
        def update(self, *args, **kwargs):
            return super().update(*args, **kwargs)

    class DummyTaskWrapper:
        def __init__(self, func, *, bind=False, name=None):
            self.__wrapped__ = func
            self.__name__ = func.__name__
            self.name = name or func.__name__
            self._bind = bind
            self.conf = DummyConf()
            self._update_state_calls = []

        def run(self, *args, **kwargs):
            if self._bind:
                return self.__wrapped__(self, *args, **kwargs)
            return self.__wrapped__(*args, **kwargs)

        def __call__(self, *args, **kwargs):
            return self.run(*args, **kwargs)

        def delay(self, *args, **kwargs): 
            return self.run(*args, **kwargs)

        def apply_async(self, args=None, kwargs=None): 
            return self.run(*(args or ()), **(kwargs or {}))

        def update_state(self, *args, **kwargs):
            self._update_state_calls.append((args, kwargs))

    class DummyCelery:
        def __init__(self, name):
            self.name = name
            self.conf = DummyConf()
            self.autodiscovered = []

        def autodiscover_tasks(self, modules):
            self.autodiscovered.extend(modules)

        def task(self, bind=False, name=None):
            def decorator(func):
                return DummyTaskWrapper(func, bind=bind, name=name)

            return decorator

    celery_stub.Celery = DummyCelery

    celery_utils = types.ModuleType("celery.utils")
    celery_utils_log = types.ModuleType("celery.utils.log")

    class DummyLogger:
        def __init__(self, name):
            self.name = name
            self.exceptions = []

        def debug(self, *args, **kwargs):
            pass

        def info(self, *args, **kwargs):
            pass

        def exception(self, *args, **kwargs):
            self.exceptions.append((args, kwargs))

    def get_task_logger(name):
        return DummyLogger(name)

    celery_utils_log.get_task_logger = get_task_logger
    celery_utils.log = celery_utils_log

    sys.modules["celery"] = celery_stub
    sys.modules["celery.utils"] = celery_utils
    sys.modules["celery.utils.log"] = celery_utils_log

importlib.reload(importlib.import_module("backend.celery_app.celery_app"))
design_task = importlib.reload(importlib.import_module("backend.tasks.design"))


class DummyGuide:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return dict(self._payload)


@pytest.fixture
def task_context(monkeypatch: pytest.MonkeyPatch):
    task = design_task.run_design_job
    calls = {"update_job": [], "update_state": []}

    def update_job(job_id, **kwargs):
        calls["update_job"].append((job_id, kwargs))
        return True

    def update_state(state, meta):
        calls["update_state"].append((state, meta))

    monkeypatch.setattr(design_task, "update_job", update_job)
    monkeypatch.setattr(task, "update_state", update_state)

    return task, calls


def test_run_design_job_success(monkeypatch: pytest.MonkeyPatch, task_context):
    task, calls = task_context

    expected_results_dir = Path(settings.CRISPRITZ_RESULTS_DIR) / "job-1"

    def fake_design(*, sequence, nuclease, pam, genome, progress_callback, crispritz_results_dir):
        assert sequence == "ACGT"
        assert nuclease == "SpCas9"
        assert crispritz_results_dir == expected_results_dir
        progress_callback(stage="identify", message="halfway", progress=0.5, details={"done": 1})
        return [DummyGuide({"protospacer": "AAA"})]

    monkeypatch.setattr(design_task, "design", fake_design)

    result = task.run(
        "job-1",
        "ACGT",
        {"nuclease": "SpCas9", "pam": "NGG", "genome": "hg38"},
    )

    assert result == {
        "guides": [{"protospacer": "AAA"}],
        "num_candidates": 1,
        "crispritz_results_dir": str(expected_results_dir),
    }

    assert len(calls["update_job"]) == 3
    assert calls["update_job"][0][1]["stage"] == "starting"
    assert calls["update_job"][1][1]["stage"] == "identify"
    assert calls["update_job"][1][1]["progress"] == 0.5
    assert calls["update_job"][2][1]["status"] == "succeeded"
    assert calls["update_job"][2][1]["payload"] == result

    assert calls["update_state"] == [
        ("PROGRESS", {"stage": "identify", "progress": 0.5})
    ]


def test_run_design_job_failure(monkeypatch: pytest.MonkeyPatch, task_context):
    task, calls = task_context

    def fake_design(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(design_task, "design", fake_design)

    with pytest.raises(RuntimeError):
        task.run(
            "job-2",
            "TTTT",
            {"nuclease": "SpCas9", "pam": "NGG", "genome": "hg38"},
        )

    assert len(calls["update_job"]) == 2
    assert calls["update_job"][0][1]["stage"] == "starting"
    failure_call = calls["update_job"][1][1]
    assert failure_call["status"] == "failed"
    assert failure_call["stage"] == "error"
    assert failure_call["message"] == "boom"
    assert failure_call["progress"] == 1.0

    assert calls["update_state"] == [("FAILURE", {"message": "boom"})]


def test_run_design_job_missing_job(monkeypatch: pytest.MonkeyPatch, task_context):
    task, calls = task_context

    def fake_update_job(job_id, **kwargs):
        calls["update_job"].append((job_id, kwargs))
        return False

    def fake_design(*, sequence, nuclease, pam, genome, progress_callback, crispritz_results_dir):
        return []

    monkeypatch.setattr(design_task, "update_job", fake_update_job)
    monkeypatch.setattr(design_task, "design", fake_design)

    with pytest.raises(design_task.JobUpdateError):
        task.run(
            "job-missing",
            "ACGT",
            {"nuclease": "SpCas9", "pam": "NGG", "genome": "hg38"},
        )

    assert calls["update_job"]
    assert calls["update_state"] == [("FAILURE", {"message": "Job job-missing no longer exists"})]


def test_run_design_job_job_store_unavailable(monkeypatch: pytest.MonkeyPatch, task_context):
    from store.jobs import JobStoreUnavailable

    task, calls = task_context

    def fake_update_job(job_id, **kwargs):
        raise JobStoreUnavailable("redis down")

    def fake_design(*, sequence, nuclease, pam, genome, progress_callback, crispritz_results_dir):
        return []

    monkeypatch.setattr(design_task, "update_job", fake_update_job)
    monkeypatch.setattr(design_task, "design", fake_design)

    with pytest.raises(design_task.JobUpdateError):
        task.run(
            "job-redis",
            "ACGT",
            {"nuclease": "SpCas9", "pam": "NGG", "genome": "hg38"},
        )

    assert calls["update_state"] == [("FAILURE", {"message": "Job store is unavailable"})]
