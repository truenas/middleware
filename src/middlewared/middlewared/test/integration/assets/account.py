import contextlib
import random
import string
import types

import pytest

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.audit import expect_audit_method_calls


@contextlib.contextmanager
def user(data):
    data.setdefault("home_create", True)  # create user homedir by default

    user = call("user.create", data)
    pk = user['id']

    try:
        yield user
    finally:
        try:
            call("user.delete", pk)
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def group(data):
    group = call("group.create", data)

    try:
        yield call("group.get_instance", group)
    finally:
        try:
            call("group.delete", group)
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def unprivileged_user(*, username, group_name, privilege_name, web_shell, roles=None):
    with group({
        "name": group_name,
    }) as g:
        with privilege({
            "name": privilege_name,
            "local_groups": [g["gid"]],
            "ds_groups": [],
            "roles": roles or [],
            "web_shell": web_shell,
        }):
            with dataset(f"{username}_homedir") as homedir:
                if web_shell:
                    # To prevent `zsh-newuser-install` interactive prompt
                    ssh(f"touch /mnt/{homedir}/.zshrc")

                password = "test1234"
                with user({
                    "username": username,
                    "full_name": "Unprivileged user",
                    "group_create": True,
                    "groups": [g["id"]],
                    "home": f"/mnt/{homedir}",
                    "password": password,
                }):
                    yield types.SimpleNamespace(username=username, password=password)


@contextlib.contextmanager
def unprivileged_user_client(roles=None):
    suffix = "".join([random.choice(string.ascii_lowercase + string.digits) for _ in range(8)])
    with unprivileged_user(
        username=f"unprivileged_{suffix}",
        group_name=f"unprivileged_users_{suffix}",
        privilege_name=f"Unprivileged users ({suffix})",
        roles=roles or [],
        web_shell=False,
    ) as t:
        with client(auth=(t.username, t.password)) as c:
            c.username = t.username
            yield c


@contextlib.contextmanager
def root_with_password_disabled():
    root_backup = call("datastore.query", "account.bsdusers", [["bsdusr_username", "=", "root"]], {"get": True})
    root_backup["bsdusr_group"] = root_backup["bsdusr_group"]["id"]
    root_backup["bsdusr_groups"] = [g["id"] for g in root_backup["bsdusr_groups"]]
    root_id = root_backup.pop("id")
    # Connect before removing root password
    with client() as c:
        try:
            c.call("datastore.update", "account.bsdusers", root_id, {"bsdusr_password_disabled": True})
            yield types.SimpleNamespace(client=c, root_id=root_id, root_backup=root_backup)
        finally:
            # Restore root access on test failure
            c.call("datastore.update", "account.bsdusers", root_id, root_backup)
            c.call("etc.generate", "user")


@pytest.fixture(scope="module")
def test_user():
    with user({
        "username": "testuser",
        "full_name": "testuser",
        "group_create": True,
        "password": "canary",
    }) as entry:
        yield entry


@contextlib.contextmanager
def temporary_update(user: dict, data: dict, with_audit: bool = False):
    """Perform a call to user.update and roll it back on teardown.

    Assume keys in `data` are a subset of the keys in `user`.

    :param user: The user entry to update.
    :param data: Fields to update with their new values.
    :param with_audit: Verify the audit logs after the first user.update call.
    """
    try:
        if with_audit:
            with expect_audit_method_calls([{
                "method": "user.update",
                "params": [user["id"], data],
                "description": f"Update user {user['username']}",
            }]):
                updated_user = call("user.update", user["id"], data)
        else:
            updated_user = call("user.update", user["id"], data)

        yield updated_user

    finally:
        call("user.update", user["id"], {k: user[k] for k in data.keys() if k in user})
