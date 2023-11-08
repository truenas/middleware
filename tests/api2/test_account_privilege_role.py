import errno
import logging

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import client

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("role", ["SNAPSHOT_READ", "SNAPSHOT_WRITE"])
def test_can_read_with_read_or_write_role(role):
    with dataset("test_snapshot_read") as ds:
        with snapshot(ds, "test"):
            with unprivileged_user_client([role]) as c:
                assert len(c.call("zfs.snapshot.query", [["dataset", "=", ds]])) == 1


def test_can_not_write_with_read_role():
    with dataset("test_snapshot_write1") as ds:
        with unprivileged_user_client(["SNAPSHOT_READ"]) as c:
            with pytest.raises(ClientException) as ve:
                c.call("zfs.snapshot.create", {
                    "dataset": ds,
                    "name": "test",
                })

            assert ve.value.errno == errno.EACCES


def test_write_with_write_role():
    with dataset("test_snapshot_write2") as ds:
        with unprivileged_user_client(["SNAPSHOT_WRITE"]) as c:
            c.call("zfs.snapshot.create", {
                "dataset": ds,
                "name": "test",
            })


def test_can_delete_with_write_role_with_separate_delete():
    with dataset("test_snapshot_delete1") as ds:
        with snapshot(ds, "test") as id:
            with unprivileged_user_client(["SNAPSHOT_DELETE"]) as c:
                c.call("zfs.snapshot.delete", id)


def test_can_not_delete_with_write_role_with_separate_delete():
    with dataset("test_snapshot_delete2") as ds:
        with snapshot(ds, "test") as id:
            with unprivileged_user_client(["SNAPSHOT_WRITE"]) as c:
                with pytest.raises(ClientException) as ve:
                    c.call("zfs.snapshot.delete", id)

                assert ve.value.errno == errno.EACCES


def test_full_admin_role():
    with unprivileged_user_client(["FULL_ADMIN"]) as c:
        c.call("system.general.config")


@pytest.mark.parametrize("role,method,params", [
    ("DATASET_READ", "pool.dataset.checksum_choices", []),
])
def test_read_role_can_call_method(role, method, params):
    with unprivileged_user_client([role]) as c:
        c.call(method, *params)


@pytest.mark.parametrize("method,params", [
    ("system.general.config", []),
    ("user.get_instance", [1]),
    ("user.query", []),
    ("user.shell_choices", []),
    ("auth.me", []),
    ("filesystem.listdir", ["/"]),
    ("filesystem.stat", ["/"]),
    ("filesystem.getacl", ["/"]),
    ("filesystem.acltemplate.by_path", [{"path": "/"}]),
    ("pool.dataset.details", []),
])
def test_readonly_can_call_method(method, params):
    with unprivileged_user_client(["READONLY"]) as c:
        c.call(method, *params)


def test_readonly_can_not_call_method():
    with unprivileged_user_client(["READONLY"]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("user.create")

        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            # fails with EPERM if API access granted
            c.call("filesystem.mkdir", "/foo")

        assert ve.value.errno == errno.EACCES


def test_limited_user_can_set_own_attributes():
    with unprivileged_user_client(["READONLY"]) as c:
        c.call("auth.set_attribute", "foo", "bar")
        attrs = c.call("auth.me")["attributes"]
        assert "foo" in attrs
        assert attrs["foo"] == "bar"


def test_limited_user_auth_token_behavior():
    with unprivileged_user_client(["READONLY"]) as c:
        auth_token = c.call("auth.generate_token")

        with client(auth=None) as c2:
            assert c2.call("auth.login_with_token", auth_token)
            c2.call("auth.me")
