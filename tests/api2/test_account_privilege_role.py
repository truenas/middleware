import errno
import logging

import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import client
from time import sleep

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.rbac


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


def test_works_for_redefined_crud_method():
    with unprivileged_user_client(["SHARING_ADMIN"]) as c:
        c.call("service.update", "cifs", {"enable": False})


def test_full_admin_role():
    with unprivileged_user_client(["FULL_ADMIN"]) as c:
        c.call("system.general.config")

        # User with FULL_ADMIN role should have something in jobs list
        assert len(c.call("core.get_jobs")) != 0

        # attempt to wait / cancel job should not fail
        jid = c.call("core.job_test", {"sleep": 1})

        c.call("core.job_wait", jid, job=True)

        c.call("core.job_abort", jid)


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
    ("core.get_jobs", []),
])
def test_readonly_can_call_method(method, params):
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        c.call(method, *params)


def test_readonly_can_not_call_method():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        with pytest.raises(ClientException) as ve:
            c.call("user.create")

        assert ve.value.errno == errno.EACCES

        with pytest.raises(ClientException) as ve:
            # fails with EPERM if API access granted
            c.call("filesystem.mkdir", "/foo")

        assert ve.value.errno == errno.EACCES


def test_limited_user_can_set_own_attributes():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        c.call("auth.set_attribute", "foo", "bar")
        attrs = c.call("auth.me")["attributes"]
        assert "foo" in attrs
        assert attrs["foo"] == "bar"


def test_limited_user_auth_token_behavior():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        auth_token = c.call("auth.generate_token")

        with client(auth=None) as c2:
            assert c2.call("auth.login_with_token", auth_token)
            c2.call("auth.me")
            c2.call("core.get_jobs")


def test_sharing_manager_jobs():
    with unprivileged_user_client(["SHARING_ADMIN"]) as c:
        auth_token = c.call("auth.generate_token")
        jid = c.call("core.job_test", {"sleep": 1})

        with client(auth=None) as c2:
            #c.call("core.job_wait", jid, job=True)
            assert c2.call("auth.login_with_token", auth_token)
            wait_job_id = c2.call("core.job_wait", jid)
            sleep(2)
            result = c2.call("core.get_jobs", [["id", "=", wait_job_id]], {"get": True})
            assert result["state"] == "SUCCESS"
            c2.call("core.job_abort", wait_job_id)


def test_foreign_job_access():
    with unprivileged_user_client(["READONLY_ADMIN"]) as unprivileged:
        with client() as c:
            job = c.call("core.job_test")

            wait_job_id = unprivileged.call("core.job_wait", job)
            sleep(2)
            result = unprivileged.call("core.get_jobs", [["id", "=", wait_job_id]], {"get": True})
            assert result["state"] != "SUCCESS"

            jobs = unprivileged.call("core.get_jobs", [["id", "=", job]])
            assert jobs == []

    with unprivileged_user_client(["FULL_ADMIN"]) as unprivileged:
        with client() as c:
            job = c.call("core.job_test")

            wait_job_id = unprivileged.call("core.job_wait", job)
            sleep(2)
            result = unprivileged.call("core.get_jobs", [["id", "=", wait_job_id]], {"get": True})
            assert result["state"] == "SUCCESS"


def test_can_not_subscribe_to_event():
    with unprivileged_user_client() as unprivileged:
        with pytest.raises(ValueError) as ve:
            unprivileged.subscribe("alert.list", lambda *args, **kwargs: None)

        assert ve.value.args[0]["errname"] == "EACCES"


def test_can_subscribe_to_event():
    with unprivileged_user_client(["READONLY_ADMIN"]) as unprivileged:
        unprivileged.subscribe("alert.list", lambda *args, **kwargs: None)
