import base64
import contextlib
import errno

import pytest

from middlewared.service_exception import ValidationErrors, ValidationError
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.keychain import localhost_ssh_credentials
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.unittest import RegexString


@contextlib.contextmanager
def task(data):
    data = {
        **data
    }

    task = call("rsynctask.create", data)

    try:
        yield task
    finally:
        call("rsynctask.delete", task["id"])


def run_task(task, timeout=120):
    call("rsynctask.run", task["id"], job=True, timeout=timeout)


@pytest.fixture(scope="module")
def localuser():
    with dataset("localuser_homedir") as localuser_homedir:
        with user({
            "username": "localuser",
            "full_name": "Local User",
            "group_create": True,
            "home": f"/mnt/{localuser_homedir}",
            "password": "test1234",
        }) as u:
            yield u


@pytest.fixture(scope="module")
def remoteuser():
    with dataset("remoteuser_homedir") as remoteuser_homedir:
        with user({
            "username": "remoteuser",
            "full_name": "Remote User",
            "group_create": True,
            "home": f"/mnt/{remoteuser_homedir}",
            "password": "test1234",
        }) as u:
            yield u


@pytest.fixture(scope="module")
def src(localuser):
    with dataset("src") as src:
        path = f"/mnt/{src}"
        ssh(f"touch {path}/test")
        ssh(f"chown -R localuser:localuser {path}")
        yield path


@pytest.fixture(scope="module")
def dst(remoteuser):
    with dataset("dst") as dst:
        path = f"/mnt/{dst}"
        ssh(f"chown -R remoteuser:remoteuser {path}")
        yield path


@pytest.fixture(scope="module")
def ssh_credentials(remoteuser):
    with localhost_ssh_credentials(username="remoteuser") as c:
        yield c


@pytest.fixture(scope="function")
def cleanup(localuser, dst):
    ssh(f"rm -rf {localuser['home']}/.ssh")
    ssh(f"rm -rf {dst}/test")


def test_no_credential_provided_create(cleanup, localuser, remoteuser, src, dst):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "remotehost": "remoteuser@localhost",
            "remoteport": 22,
            "mode": "SSH",
            "remotepath": dst,
        }):
            pass

    assert e.value.errors == [
        ValidationError(
            "rsync_task_create.user",
            RegexString(".*you need a user with a private key.*"),
            errno.EINVAL,
        )
    ]


def test_home_directory_key_invalid_permissions(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    ssh(f"mkdir {localuser['home']}/.ssh")
    ssh(f"ssh-keyscan localhost >> {localuser['home']}/.ssh/known_hosts")
    call(
        "filesystem.file_receive",
        f"{localuser['home']}/.ssh/id_rsa",
        base64.b64encode(ssh_credentials["keypair"]["attributes"]["private_key"].encode("ascii")).decode("ascii"),
        {"mode": 0o0644},
    )
    ssh(f"chown -R localuser:localuser {localuser['home']}/.ssh")

    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "remotehost": "remoteuser@localhost",
            "remoteport": 22,
            "mode": "SSH",
            "remotepath": dst,
        }):
            pass

    assert e.value.errors == [
        ValidationError(
            "rsync_task_create.user",
            RegexString("Permissions 644 .* are too open.*"),
            errno.EINVAL,
        )
    ]


def test_home_directory_key(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    ssh(f"mkdir {localuser['home']}/.ssh")
    ssh(f"ssh-keyscan localhost >> {localuser['home']}/.ssh/known_hosts")
    call(
        "filesystem.file_receive",
        f"{localuser['home']}/.ssh/id_rsa",
        base64.b64encode(ssh_credentials["keypair"]["attributes"]["private_key"].encode("ascii")).decode("ascii"),
        {"mode": 0o600},
    )
    ssh(f"chown -R localuser:localuser {localuser['home']}/.ssh")

    with task({
        "path": f"{src}/",
        "user": "localuser",
        "remotehost": "remoteuser@localhost",
        "remoteport": 22,
        "mode": "SSH",
        "remotepath": dst,
    }) as t:
        run_task(t)

    assert ssh(f"ls -1 {dst}") == "test\n"


def test_ssh_credentials_key(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": dst,
    }) as t:
        run_task(t)

    assert ssh(f"ls -1 {dst}") == "test\n"


def test_ssh_credentials_delete(cleanup, localuser, remoteuser, src, dst):
    with localhost_ssh_credentials(username="remoteuser") as c:
        path = f"{src}/"
        with task({
            "path": path,
            "user": "localuser",
            "ssh_credentials": c["credentials"]["id"],
            "mode": "SSH",
            "remotepath": dst,
        }) as t:
            assert call("keychaincredential.used_by", c["credentials"]["id"]) == [
                {"title": f"Rsync task for {path!r}", "unbind_method": "disable"},
            ]

            call("keychaincredential.delete", c["credentials"]["id"], {"cascade": True})

            t = call("rsynctask.get_instance", t["id"])
            assert not t["enabled"]
