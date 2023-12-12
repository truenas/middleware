import pytest

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.pool import dataset, snapshot


@pytest.fixture(scope="module")
def readonly_client():
    with unprivileged_user_client(["READONLY"]) as c:
        yield c
    with dataset("test_snapshot_read") as ds:
        with snapshot(ds, "test"):
            with unprivileged_user_client([role]) as c:
                assert len(c.call("zfs.snapshot.query", [["dataset", "=", ds]])) == 1


def test_user_query_multiple(readonly_client):
    assert readonly_client.call("user.query", [["id", "=", 1]])[0]["unixhash"] == "********"


def test_user_query_single(readonly_client):
    assert readonly_client.call("user.query", [["id", "=", 1]], {"get": True})["unixhash"] == "********"


def test_user_get_instance(readonly_client):
    assert readonly_client.call("user.get_instance", 1)["unixhash"] == "********"
