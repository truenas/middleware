import errno
import logging

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.pool import dataset, snapshot

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("role", ["SNAPSHOT_READ", "SNAPSHOT_WRITE"])
def test_can_read_with_read_or_write_role(role):
    with dataset("test") as ds:
        with snapshot(ds, "test"):
            with unprivileged_user_client([role]) as c:
                assert len(c.call("zfs.snapshot.query", [["dataset", "=", ds]])) == 1


def test_can_not_write_with_read_role():
    with dataset("test") as ds:
        with unprivileged_user_client(["SNAPSHOT_READ"]) as c:
            with pytest.raises(ClientException) as ve:
                c.call("zfs.snapshot.create", {
                    "dataset": ds,
                    "name": "test",
                })

            assert ve.value.errno == errno.EACCES


def test_write_with_write_role():
    with dataset("test") as ds:
        with unprivileged_user_client(["SNAPSHOT_WRITE"]) as c:
            c.call("zfs.snapshot.create", {
                "dataset": ds,
                "name": "test",
            })


def test_can_delete_with_write_role_with_separate_delete():
    with dataset("test") as ds:
        with snapshot(ds, "test") as id:
            with unprivileged_user_client(["SNAPSHOT_DELETE"]) as c:
                c.call("zfs.snapshot.delete", id)


def test_can_not_delete_with_write_role_with_separate_delete():
    with dataset("test") as ds:
        with snapshot(ds, "test") as id:
            with unprivileged_user_client(["SNAPSHOT_WRITE"]) as c:
                with pytest.raises(ClientException) as ve:
                    c.call("zfs.snapshot.delete", id)

                assert ve.value.errno == errno.EACCES
