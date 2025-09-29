import os
import shutil
import sys
import types
from pathlib import Path

import pytest

from api.routes import design as design_route
import services.design as design_service
import services.crispritz as crispritz
from backend.tasks import design as design_task

INTEGRATION = os.getenv("RUN_INTEGRATION") == "1"

# Lightweight Celery stub 
if "celery" not in sys.modules:
    celery_stub = types.ModuleType("celery")

    class DummyTaskWrapper:
        def __init__(self, func, *, bind=False, name=None):
            self.__wrapped__ = func
            self.__name__ = func.__name__
            self.name = name or func.__name__
            self._bind = bind

        def run(self, *args, **kwargs):
            if self._bind:
                return self.__wrapped__(self, *args, **kwargs)
            return self.__wrapped__(*args, **kwargs)

        def apply_async(self, args=None, kwargs=None):
            return self.run(*(args or ()), **(kwargs or {}))

    class DummyCelery:
        def __init__(self, name):
            self.name = name
            self.conf = {}

        def autodiscover_tasks(self, modules):
            return None

        def task(self, bind=False, name=None):
            def decorator(func):
                return DummyTaskWrapper(func, bind=bind, name=name)

            return decorator

    celery_utils = types.ModuleType("celery.utils")
    celery_utils_log = types.ModuleType("celery.utils.log")

    def get_task_logger(name):
        class _Logger:
            def exception(self, *args, **kwargs):
                pass

        return _Logger()

    celery_utils_log.get_task_logger = get_task_logger
    celery_utils.log = celery_utils_log

    celery_stub.Celery = DummyCelery

    sys.modules["celery"] = celery_stub
    sys.modules["celery.utils"] = celery_utils
    sys.modules["celery.utils.log"] = celery_utils_log


@pytest.mark.integration
@pytest.mark.skipif(not INTEGRATION, reason="set RUN_INTEGRATION=1 to run")
def test_design_endpoint_integration_with_crispritz(client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    data_dir = Path(__file__).resolve().parent.parent / "data" / "crispritz"
    targets_src = data_dir / "out.targets.txt"
    profile_src = data_dir / "out.profile.xls"
    assert targets_src.exists() and profile_src.exists(), "Provide CRISPRitz sample outputs under tests/data/crispritz"

    create_calls = []
    updates = []
    state_updates = []

    def fake_create_job(**kwargs):
        create_calls.append(kwargs)
        return "job-int"

    def fake_update_job(job_id, **kwargs):
        updates.append((job_id, kwargs))
        return True

    def fake_run_crispritz(candidates, wt_lookup, progress_callback=None, results_dir=None):
        base_dir = Path(results_dir or (tmp_path / "crispritz"))
        outputs_dir = base_dir / "outputs"
        outputs_dir.mkdir(exist_ok=True, parents=True)
        # Provide both annotated and raw filenames so either read path works
        shutil.copy(targets_src, outputs_dir / "out.Annotation.targets.txt")
        shutil.copy(targets_src, outputs_dir / "out.targets.txt")
        shutil.copy(profile_src, outputs_dir / "out.profile.xls")
        summaries = crispritz._parse_crispritz_results(outputs_dir, wt_lookup)
        if progress_callback:
            progress_callback(
                stage="crispritz:results_ready",
                message="mocked",
                progress=0.58,
                details={"crispritz_results_dir": str(base_dir)},
            )
        return summaries

    def fake_score_rs3(context_30mer: str):
        return 0.42

    task = design_task.run_design_job

    monkeypatch.setattr(design_route, "create_job", fake_create_job)
    monkeypatch.setattr(design_route, "find_cached_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(design_task, "update_job", fake_update_job)
    monkeypatch.setattr(design_service, "run_crispritz", fake_run_crispritz)
    monkeypatch.setattr(design_service, "_score_rs3", fake_score_rs3)
    monkeypatch.setattr(crispritz, "calc_cfd", lambda wt, off: 0.1)

    job_results_root = tmp_path / "results"
    monkeypatch.setattr(design_task.settings, "CRISPRITZ_RESULTS_DIR", str(job_results_root))

    def capture_update_state(state, meta):
        state_updates.append((state, meta))

    monkeypatch.setattr(task, "update_state", capture_update_state)

    def fake_apply_async(*, kwargs):
        return task.run(kwargs["job_id"], kwargs["sequence"], kwargs["request_payload"])

    monkeypatch.setattr(design_route.run_design_job, "apply_async", fake_apply_async)

    payload = {
        "sequence": "GAGTCCGAGCAGAAGAAGAAGGG",
        "nuclease": "SpCas9",
        "pam": "NGG",
        "genome": "hg38",
    }

    response = client.post("/api/design", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-int"
    assert body["status"] == "queued"

    assert create_calls, "create_job should have been called"
    assert create_calls[0]["input_hash"]
    assert create_calls[0]["request_payload"]["sequence"] == payload["sequence"]
    assert updates, "update_job should have recorded calls"

    final_job = updates[-1][1]
    assert final_job["status"] == "succeeded"
    assert final_job["details"]["total_guides"] == 1
    assert final_job["details"]["completed_guides"] == 1
    assert final_job["details"]["crispritz_results_dir"] == str(job_results_root / "job-int")
    assert final_job["payload"]["num_candidates"] == 1
    assert final_job["payload"]["crispritz_results_dir"] == str(job_results_root / "job-int")
    guide = final_job["payload"]["guides"][0]
    assert guide["protospacer"] == "GAGTCCGAGCAGAAGAAGAA"
    assert guide["rs3_score"] == pytest.approx(0.42)

    assert state_updates
