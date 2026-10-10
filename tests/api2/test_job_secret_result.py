import errno

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call

REDACTED = "********"
SECRET = "canary"
DICT = {"username": "bob", "password": SECRET}
REDACTED_DICT = {"username": "bob", "password": REDACTED}

METHODS = [
    ("test.test_secret", SECRET, REDACTED),
    ("test.test_secret_object", SECRET, REDACTED),
    ("test.test_secret_dict", DICT, REDACTED_DICT),
]
JOBS = [
    ("test.test_secret_job", SECRET, REDACTED),
    ("test.test_secret_object_job", SECRET, REDACTED),
    ("test.test_secret_dict_job", DICT, REDACTED_DICT),
]


@pytest.fixture(scope="module")
def readonly_client():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        yield c


@pytest.mark.parametrize("method,exposed,_redacted", METHODS)
def test_method_exposes_secret_to_full_admin(method, exposed, _redacted):
    assert call(method) == exposed


@pytest.mark.parametrize("method,exposed,_redacted", JOBS)
def test_job_exposes_secret_to_full_admin(method, exposed, _redacted):
    assert call(method, job=True) == exposed


@pytest.mark.parametrize("method,_exposed,redacted", METHODS)
def test_method_redacts_secret(readonly_client, method, _exposed, redacted):
    assert readonly_client.call(method) == redacted


@pytest.mark.parametrize("method,_exposed,redacted", JOBS)
def test_job_redacts_secret(readonly_client, method, _exposed, redacted):
    assert readonly_client.call(method, job=True) == redacted


@pytest.mark.parametrize("method,_exposed,redacted", JOBS)
def test_job_redacts_secret_in_events(readonly_client, method, _exposed, redacted):
    events = []
    readonly_client.subscribe("core.get_jobs", lambda *args, **kwargs: events.append(kwargs), sync=True)
    try:
        job_id = readonly_client.call(method)
        readonly_client.call("core.job_wait", job_id, job=True)
    finally:
        readonly_client.unsubscribe("core.get_jobs")

    results = [e["fields"]["result"] for e in events if e["fields"]["id"] == job_id]
    assert results
    assert all(result in (None, redacted) for result in results), results


@pytest.mark.parametrize("method,exposed,redacted", JOBS)
def test_job_result_in_get_jobs(method, exposed, redacted):
    job_id = call(method)
    call("core.job_wait", job_id, job=True)

    assert call("core.get_jobs", [["id", "=", job_id]], {"get": True})["result"] == redacted
    assert (
        call(
            "core.get_jobs",
            [["id", "=", job_id]],
            {"get": True, "extra": {"raw_result": True}},
        )["result"]
        == exposed
    )


@pytest.mark.parametrize("method,_exposed,redacted", JOBS)
def test_job_redacts_secret_in_get_jobs(readonly_client, method, _exposed, redacted):
    job_id = readonly_client.call(method)
    readonly_client.call("core.job_wait", job_id, job=True)

    assert readonly_client.call("core.get_jobs", [["id", "=", job_id]], {"get": True})["result"] == redacted


def test_get_jobs_rejects_raw_result_without_full_admin(readonly_client):
    with pytest.raises(CallError) as ve:
        readonly_client.call("core.get_jobs", [], {"extra": {"raw_result": True}})

    assert ve.value.errno == errno.EPERM


@pytest.mark.parametrize("method,exposed,_redacted", JOBS)
def test_core_bulk_serializes_job_result(method, exposed, _redacted):
    assert call("core.bulk", method, [[]], job=True)[0]["result"] == exposed
