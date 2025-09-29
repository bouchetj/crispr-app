import sys
import types
import importlib
from datetime import datetime, timedelta, timezone

import pytest

# Redis stubs
if "redis" not in sys.modules:
    redis_stub = types.ModuleType("redis")

    class RedisPlaceholder:
        @classmethod
        def from_url(cls, url, decode_responses=True):
            raise NotImplementedError("Redis.from_url needs to be patched in tests")

    redis_stub.Redis = RedisPlaceholder

    exceptions_stub = types.ModuleType("redis.exceptions")

    class RedisError(Exception):
        pass

    exceptions_stub.RedisError = RedisError

    sys.modules["redis"] = redis_stub
    sys.modules["redis.exceptions"] = exceptions_stub

backend_store_jobs = importlib.import_module("store.jobs")


@pytest.fixture(autouse=True)
def reset_redis_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(backend_store_jobs, "_REDIS_CLIENT", None)
    yield
    monkeypatch.setattr(backend_store_jobs, "_REDIS_CLIENT", None)


class FakeRedisClient:
    def __init__(self):
        self.storage = {}
        self.sorted_sets = {}
        self.hashes = {}
        self.ping_called = False

    def ping(self):
        self.ping_called = True

    def set(self, key, value):
        self.storage[key] = value

    def get(self, key):
        return self.storage.get(key)

    def keys(self, pattern):
        if pattern == "jobs:*":
            matches = [key for key in self.storage if key.startswith("jobs:")]
            matches.extend(key for key in self.sorted_sets if key.startswith("jobs:"))
            matches.extend(key for key in self.hashes if key.startswith("jobs:"))
            return matches
        return []

    def delete(self, *keys):
        for key in keys:
            self.storage.pop(key, None)
            self.sorted_sets.pop(key, None)
            self.hashes.pop(key, None)

    def zadd(self, key, mapping):
        zset = self.sorted_sets.setdefault(key, {})
        for member, score in mapping.items():
            zset[member] = score

    def zrevrange(self, key, start, end):
        items = sorted(
            self.sorted_sets.get(key, {}).items(),
            key=lambda kv: (-kv[1], kv[0]),
        )
        if not items:
            return []
        size = len(items)
        if end < 0:
            end = size + end
        end = min(end, size - 1)
        if start < 0:
            start = size + start
        if start < 0:
            start = 0
        if start > end:
            return []
        return [items[i][0] for i in range(start, end + 1)]

    def zrem(self, key, member):
        self.sorted_sets.get(key, {}).pop(member, None)

    def hset(self, key, field, value):
        mapping = self.hashes.setdefault(key, {})
        mapping[field] = value
        return 1

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hdel(self, key, field):
        mapping = self.hashes.get(key)
        if mapping and field in mapping:
            del mapping[field]
            if not mapping:
                self.hashes.pop(key, None)


class FakeRedis:
    last_instance: FakeRedisClient | None = None

    @classmethod
    def from_url(cls, url, decode_responses=True):
        client = FakeRedisClient()
        client.url = url
        cls.last_instance = client
        return client


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(backend_store_jobs, "Redis", FakeRedis)
    monkeypatch.setattr(backend_store_jobs.settings, "JOBS_REDIS_URL", "redis://test")
    FakeRedis.last_instance = None
    return FakeRedis


def test_utcnow_is_timezone_aware():
    now = backend_store_jobs._utcnow()
    assert isinstance(now, datetime)
    assert now.tzinfo is not None


def test_normalize_progress_clamps_values():
    assert backend_store_jobs._normalize_progress(None) is None
    assert backend_store_jobs._normalize_progress(-0.5) == 0.0
    assert backend_store_jobs._normalize_progress(0.4) == 0.4
    assert backend_store_jobs._normalize_progress(5.0) == 1.0


def test_job_key_prefixes_identifier():
    assert backend_store_jobs._job_key("abc") == "jobs:abc"


def test_serialize_and_deserialize_preserve_timestamps():
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    payload = {"created_at": now, "updated_at": now, "status": "queued"}
    raw = backend_store_jobs._serialize_job(payload)
    restored = backend_store_jobs._deserialize_job(raw)
    assert restored["created_at"] == now
    assert restored["updated_at"] == now
    assert restored["status"] == "queued"


def test_ensure_redis_returns_cached(monkeypatch: pytest.MonkeyPatch):
    cached = FakeRedisClient()
    monkeypatch.setattr(backend_store_jobs, "_REDIS_CLIENT", cached)
    assert backend_store_jobs._ensure_redis() is cached


def test_ensure_redis_requires_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(backend_store_jobs.settings, "JOBS_REDIS_URL", "")
    with pytest.raises(backend_store_jobs.JobStoreUnavailable):
        backend_store_jobs._ensure_redis()


def test_ensure_redis_connection_failure(monkeypatch: pytest.MonkeyPatch):
    class BrokenRedis:
        @classmethod
        def from_url(cls, url, decode_responses=True):
            class _Client:
                def ping(self):
                    from redis.exceptions import RedisError

                    raise RedisError("fail")

            return _Client()

    monkeypatch.setattr(backend_store_jobs, "Redis", BrokenRedis)
    monkeypatch.setattr(backend_store_jobs.settings, "JOBS_REDIS_URL", "redis://bad")
    with pytest.raises(backend_store_jobs.JobStoreUnavailable):
        backend_store_jobs._ensure_redis()


def test_create_and_get_job(fake_redis):
    job_id = backend_store_jobs.create_job(
        status="running",
        progress=1.5,
        details={"foo": "bar"},
        payload={"guides": []},
        input_hash="abc",
        request_payload={"sequence": "AAA"},
    )
    assert job_id

    client = fake_redis.last_instance
    assert client is not None
    stored = backend_store_jobs._deserialize_job(client.storage[backend_store_jobs._job_key(job_id)])
    assert stored["status"] == "running"
    assert stored["progress"] == 1.0
    assert stored["details"] == {"foo": "bar"}
    assert stored["payload"] == {"guides": []}
    assert stored["cached"] is False
    assert stored["input_hash"] == "abc"
    assert stored["request_payload"] == {"sequence": "AAA"}
    assert client.sorted_sets[backend_store_jobs._JOB_INDEX_KEY][job_id] == pytest.approx(stored["created_at"].timestamp())

    job = backend_store_jobs.get_job(job_id)
    assert job is not None
    job["details"]["foo"] = "changed"
    job_again = backend_store_jobs.get_job(job_id)
    assert job_again["details"]["foo"] == "bar"


def test_get_job_missing_returns_none(fake_redis):
    fake_redis.from_url("redis://test")
    assert backend_store_jobs.get_job("missing") is None


def test_update_job_updates_fields(fake_redis):
    job_id = backend_store_jobs.create_job(status="queued", progress=0.2, input_hash="xyz")
    updated = backend_store_jobs.update_job(
        job_id,
        status="succeeded",
        progress=1.5,
        message="done",
        stage="finished",
        details={"count": 1},
        payload={"guides": [1]},
    )
    assert updated is True

    client = fake_redis.last_instance
    job = backend_store_jobs._deserialize_job(client.storage[backend_store_jobs._job_key(job_id)])
    assert job["status"] == "succeeded"
    assert job["progress"] == 1.0
    assert job["message"] == "done"
    assert job["stage"] == "finished"
    assert job["details"] == {"count": 1}
    assert job["payload"] == {"guides": [1]}
    assert job["updated_at"] >= job["created_at"]
    assert job["cached"] is True
    assert client.hashes[backend_store_jobs._JOB_INPUT_HASH_KEY]["xyz"] == job_id


def test_update_job_missing_returns_false(fake_redis):
    assert backend_store_jobs.update_job("missing", status="running") is False


def test_reset_jobs_removes_all(fake_redis):
    backend_store_jobs.create_job()
    backend_store_jobs.create_job()
    client = fake_redis.last_instance
    assert client.keys("jobs:*")
    backend_store_jobs.reset_jobs()
    assert client.keys("jobs:*") == []
    assert client.sorted_sets.get(backend_store_jobs._JOB_INDEX_KEY) in (None, {})
    assert client.hashes.get(backend_store_jobs._JOB_INPUT_HASH_KEY) in (None, {})


def test_list_jobs_returns_most_recent_first(fake_redis, monkeypatch: pytest.MonkeyPatch):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    counter = {"value": 0}

    def fake_now():
        value = base + timedelta(seconds=counter["value"])
        counter["value"] += 1
        return value

    monkeypatch.setattr(backend_store_jobs, "_utcnow", fake_now)

    job_one = backend_store_jobs.create_job(status="queued")
    job_two = backend_store_jobs.create_job(status="running")
    job_three = backend_store_jobs.create_job(status="failed")

    jobs = backend_store_jobs.list_jobs(limit=2)
    assert [job["job_id"] for job in jobs] == [job_three, job_two]


def test_find_cached_job_returns_succeeded_job(fake_redis):
    job_id = backend_store_jobs.create_job(status="queued", input_hash="sig")
    assert backend_store_jobs.find_cached_job("sig") is None

    backend_store_jobs.update_job(job_id, status="succeeded", payload={"result": 1})

    cached = backend_store_jobs.find_cached_job("sig")
    assert cached is not None
    assert cached["job_id"] == job_id
    assert cached["status"] == "succeeded"
    assert cached["cached"] is True


def test_find_cached_job_clears_missing_entries(fake_redis):
    client = backend_store_jobs._ensure_redis()
    client.hset(backend_store_jobs._JOB_INPUT_HASH_KEY, "sig", "missing")

    cached = backend_store_jobs.find_cached_job("sig")
    assert cached is None
    assert backend_store_jobs._JOB_INPUT_HASH_KEY not in client.hashes or "sig" not in client.hashes.get(backend_store_jobs._JOB_INPUT_HASH_KEY, {})
