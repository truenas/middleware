import base64
import contextlib
import errno
import uuid
from unittest.mock import ANY

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


@pytest.fixture(scope="module")
def ipv6_ssh_credentials(remoteuser):
    with localhost_ssh_credentials(url="http://[::1]", username="remoteuser") as c:
        yield c


@pytest.fixture(scope="function")
def cleanup(localuser, src, dst):
    ssh(f"rm -rf {localuser['home']}/.ssh")
    ssh(f"rm -rf {src}/*", check=False)
    ssh(f"touch {src}/test")
    ssh(f"chown -R localuser:localuser {src}")
    ssh(f"rm -rf {dst}/*", check=False)


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


@pytest.mark.parametrize("validate_rpath", [True, False])
def test_home_directory_key_not_in_known_hosts(cleanup, localuser, remoteuser, src, dst, ssh_credentials,
                                               validate_rpath):
    ssh(f"mkdir {localuser['home']}/.ssh")
    call(
        "filesystem.file_receive",
        f"{localuser['home']}/.ssh/id_rsa",
        base64.b64encode(ssh_credentials["keypair"]["attributes"]["private_key"].encode("ascii")).decode("ascii"),
        {"mode": 0o600},
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
            "validate_rpath": validate_rpath,
        }):
            pass

    assert e.value.errors == [
        ValidationError(
            "rsync_task_create.remotehost",
            ANY,
            ValidationError.ESSLCERTVERIFICATIONERROR,
        )
    ]


def test_ssh_keyscan_does_not_duplicate_host_keys(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    ssh(f"mkdir {localuser['home']}/.ssh")
    ssh(f"ssh-keyscan localhost >> {localuser['home']}/.ssh/known_hosts")
    call(
        "filesystem.file_receive",
        f"{localuser['home']}/.ssh/id_rsa",
        base64.b64encode(ssh_credentials["keypair"]["attributes"]["private_key"].encode("ascii")).decode("ascii"),
        {"mode": 0o600},
    )
    ssh(f"chown -R localuser:localuser {localuser['home']}/.ssh")

    known_hosts = ssh(f"cat {localuser['home']}/.ssh/known_hosts")

    with task({
        "path": f"{src}/",
        "user": "localuser",
        "remotehost": "remoteuser@localhost",
        "remoteport": 22,
        "mode": "SSH",
        "remotepath": dst,
        "ssh_keyscan": True,
    }) as t:
        pass

    assert ssh(f"cat {localuser['home']}/.ssh/known_hosts") == known_hosts


def test_home_directory_key(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    ssh(f"mkdir {localuser['home']}/.ssh")
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
        "ssh_keyscan": True,
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
        assert t['dataset'] == src.removeprefix('/mnt/')
        assert t['relative_path'] == ''

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


def test_state_persist(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": dst,
    }) as t:
        run_task(t)

        row = call("datastore.query", "tasks.rsync", [["id", "=", t["id"]]], {"get": True})
        assert row["rsync_job"]["state"] == "SUCCESS"


def test_local_path_with_whitespace(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    src = f"{src}/work stuff"
    ssh(f"mkdir '{src}'")
    ssh(f"touch '{src}/test2'")
    ssh(f"chown -R localuser:localuser '{src}'")
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": dst,
    }) as t:
        run_task(t)

    assert ssh(f"ls -1 '{dst}'") == "test2\n"


def test_remotepath_with_whitespace(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    dst = f"{dst}/work stuff"
    ssh(f"mkdir '{dst}'")
    ssh(f"chown remoteuser:remoteuser '{dst}'")
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": dst,
    }) as t:
        run_task(t)

    assert ssh(f"ls -1 '{dst}'") == "test\n"


def test_ipv6_ssh_credentials(cleanup, localuser, remoteuser, src, dst, ipv6_ssh_credentials):
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ipv6_ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": dst,
    }) as t:
        run_task(t)

    assert ssh(f"ls -1 {dst}") == "test\n"


def test_validate_rpath(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": f"{dst}/",
        "validate_rpath": True,
    }):
        pass


def test_validate_rpath_does_not_exist(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "ssh_credentials": ssh_credentials["credentials"]["id"],
            "mode": "SSH",
            "remotepath": f"{dst}/nonexistent/",
            "validate_rpath": True,
        }):
            pass

    assert e.value.errors == [
        ValidationError(
            "rsync_task_create.remotepath",
            RegexString("The Remote Path you specified does not exist or is not a directory.*"),
            errno.EINVAL,
        )
    ]


def test_keyscan(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": f"{dst}/",
        "validate_rpath": False,
    }):
        pass


def install_home_directory_key(localuser, ssh_credentials):
    """Place the credential's private key into the local user's home directory with correct permissions."""
    ssh(f"mkdir {localuser['home']}/.ssh")
    call(
        "filesystem.file_receive",
        f"{localuser['home']}/.ssh/id_rsa",
        base64.b64encode(ssh_credentials["keypair"]["attributes"]["private_key"].encode("ascii")).decode("ascii"),
        {"mode": 0o600},
    )
    ssh(f"chown -R localuser:localuser {localuser['home']}/.ssh")


def find_rsync_alert(klass, task_id):
    for alert in call("alert.list"):
        if alert["klass"] == klass and (alert.get("args") or {}).get("id") == task_id:
            return alert
    return None


# ---------------------------------------------------------------------------
# General validation (validate.py: validate_rsync_task)
# ---------------------------------------------------------------------------


def test_user_with_spaces(cleanup, localuser, src, dst):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "local user",
            "mode": "MODULE",
            "remotehost": "127.0.0.1",
            "remotemodule": "test",
        }):
            pass

    assert e.value.errors == [
        ValidationError("rsync_task_create.user", "User names cannot have spaces", errno.EINVAL),
    ]


def test_nonexistent_user(cleanup, src, dst):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "nonexistent_user_xyz",
            "mode": "MODULE",
            "remotehost": "127.0.0.1",
            "remotemodule": "test",
        }):
            pass

    assert e.value.errors == [
        ValidationError(
            "rsync_task_create.user",
            RegexString('Provided user "nonexistent_user_xyz" does not exist'),
            errno.EINVAL,
        ),
    ]


def test_invalid_extra(cleanup, localuser, src, dst):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "mode": "MODULE",
            "remotehost": "127.0.0.1",
            "remotemodule": "test",
            "extra": ['"'],
        }):
            pass

    assert e.value.errors == [
        ValidationError(
            "rsync_task_create.extra",
            RegexString("Please specify valid value.*"),
            errno.EINVAL,
        ),
    ]


# ---------------------------------------------------------------------------
# MODULE mode validation and command building (validate.py + task.py)
# ---------------------------------------------------------------------------


def test_module_required_fields(cleanup, localuser, src, dst):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "mode": "MODULE",
        }):
            pass

    attributes = {error.attribute for error in e.value.errors}
    assert "rsync_task_create.remotehost" in attributes
    assert "rsync_task_create.remotemodule" in attributes


def test_module_ssh_credentials_not_allowed(cleanup, localuser, src, dst, ssh_credentials):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "mode": "MODULE",
            "remotehost": "127.0.0.1",
            "remotemodule": "test",
            "ssh_credentials": ssh_credentials["credentials"]["id"],
        }):
            pass

    assert e.value.errors == [
        ValidationError(
            "rsync_task_create.ssh_credentials",
            "SSH credentials can't be used when mode is MODULE",
            errno.EINVAL,
        ),
    ]


@pytest.mark.parametrize("direction", ["PUSH", "PULL"])
def test_module_run_failure(cleanup, localuser, src, dst, direction):
    """Running a MODULE task against a host with no rsync daemon fails and raises a RsyncFailed alert."""
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "mode": "MODULE",
        "remotehost": "127.0.0.1",
        "remotemodule": "nonexistent_module_xyz",
        "direction": direction,
    }) as t:
        with pytest.raises(Exception, match="rsync command returned"):
            run_task(t)

        assert find_rsync_alert("RsyncFailed", t["id"]) is not None

    call("alert.oneshot_delete", "RsyncFailed", t["id"])


def test_module_run_failure_quiet(cleanup, localuser, src, dst):
    """A quiet task that fails raises an error but does not create a RsyncFailed alert."""
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "mode": "MODULE",
        "remotehost": "127.0.0.1",
        "remotemodule": "nonexistent_module_xyz",
        "quiet": True,
    }) as t:
        with pytest.raises(Exception, match="rsync command returned"):
            run_task(t)

        assert find_rsync_alert("RsyncFailed", t["id"]) is None


def test_module_update(cleanup, localuser, src, dst):
    """Updating a task without SSH credentials exercises the non-credentials update path."""
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "mode": "MODULE",
        "remotehost": "127.0.0.1",
        "remotemodule": "test",
    }) as t:
        updated = call("rsynctask.update", t["id"], {"desc": "updated description"})
        assert updated["desc"] == "updated description"


def test_extra_value_split_on_query(cleanup, localuser, src, dst):
    """A misconfigured (unsplittable) ``extra`` value stored in the database is handled gracefully on query."""
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "mode": "MODULE",
        "remotehost": "127.0.0.1",
        "remotemodule": "test",
    }) as t:
        # Bypass create validation to store a value that ``shlex.split`` cannot parse
        call("datastore.update", "tasks.rsync", t["id"], {"rsync_extra": '"'})
        instance = call("rsynctask.get_instance", t["id"])
        assert instance["extra"] == ['"']


# ---------------------------------------------------------------------------
# SSH mode validation (validate.py: validate_ssh_task / get_connect_kwargs)
# ---------------------------------------------------------------------------


def test_invalid_ssh_credentials(cleanup, localuser, src, dst):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "mode": "SSH",
            "ssh_credentials": 99999999,
            "remotepath": dst,
        }):
            pass

    assert e.value.errors == [
        ValidationError("rsync_task_create.ssh_credentials", ANY, errno.EINVAL),
    ]


def test_ssh_credentials_without_private_key(cleanup, localuser, remoteuser, src, dst):
    """SSH credentials whose key pair has no private key produce a validation error."""
    generated = call("keychaincredential.generate_ssh_key_pair")
    keypair = call("keychaincredential.create", {
        "name": str(uuid.uuid4()),
        "type": "SSH_KEY_PAIR",
        "attributes": {"public_key": generated["public_key"]},
    })
    try:
        credentials = call("keychaincredential.create", {
            "name": str(uuid.uuid4()),
            "type": "SSH_CREDENTIALS",
            "attributes": {
                "host": "localhost",
                "port": 22,
                "username": "remoteuser",
                "private_key": keypair["id"],
                "remote_host_key": generated["public_key"],
            },
        })
        try:
            with pytest.raises(ValidationErrors) as e:
                with task({
                    "path": f"{src}/",
                    "user": "localuser",
                    "mode": "SSH",
                    "ssh_credentials": credentials["id"],
                    "remotepath": dst,
                }):
                    pass

            assert e.value.errors == [
                ValidationError(
                    "rsync_task_create.ssh_credentials",
                    "SSH key pair has no private key",
                    errno.EINVAL,
                ),
            ]
        finally:
            call("keychaincredential.delete", credentials["id"], {"cascade": True})
    finally:
        with contextlib.suppress(Exception):
            call("keychaincredential.delete", keypair["id"])


def test_ssh_authentication_failure(cleanup, localuser, remoteuser, src, dst):
    """A key that is not authorized on the remote host fails remote path validation."""
    generated = call("keychaincredential.generate_ssh_key_pair")
    ssh(f"mkdir {localuser['home']}/.ssh")
    call(
        "filesystem.file_receive",
        f"{localuser['home']}/.ssh/id_rsa",
        base64.b64encode(generated["private_key"].encode("ascii")).decode("ascii"),
        {"mode": 0o600},
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
            "ssh_keyscan": True,
            "validate_rpath": True,
        }):
            pass

    assert e.value.errors == [
        ValidationError("rsync_task_create.remotehost", ANY, errno.EINVAL),
    ]


def test_ssh_remotepath_required(cleanup, localuser, src, dst, ssh_credentials):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "mode": "SSH",
            "ssh_credentials": ssh_credentials["credentials"]["id"],
            "remotepath": "",
        }):
            pass

    assert e.value.errors == [
        ValidationError("rsync_task_create.remotepath", "This field is required", errno.EINVAL),
    ]


def test_ssh_remotehost_and_remoteport_required(cleanup, localuser, src, dst):
    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "mode": "SSH",
            "remotepath": dst,
        }):
            pass

    attributes = {error.attribute for error in e.value.errors}
    assert "rsync_task_create.remotehost" in attributes
    assert "rsync_task_create.remoteport" in attributes


def test_ssh_remotehost_required_with_home_directory_key(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    """A valid home directory key but no remotehost yields a clean validation error (not a crash)."""
    install_home_directory_key(localuser, ssh_credentials)

    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "remoteport": 22,
            "mode": "SSH",
            "remotepath": dst,
        }):
            pass

    assert e.value.errors == [
        ValidationError("rsync_task_create.remotehost", "This field is required", errno.EINVAL),
    ]


def test_ssh_remote_username_from_user_field(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    """When the remote host has no ``user@`` prefix, the ``user`` field is used as the remote username."""
    install_home_directory_key(localuser, ssh_credentials)

    with task({
        "path": f"{src}/",
        "user": "localuser",
        "remotehost": "localhost",
        "remoteport": 22,
        "mode": "SSH",
        "remotepath": dst,
        "ssh_keyscan": True,
        "validate_rpath": False,
    }):
        pass


def test_ssh_invalid_known_hosts(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    install_home_directory_key(localuser, ssh_credentials)
    ssh(f"echo -n invalidentry > {localuser['home']}/.ssh/known_hosts")
    ssh(f"chown localuser:localuser {localuser['home']}/.ssh/known_hosts")

    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "remotehost": "remoteuser@localhost",
            "remoteport": 22,
            "mode": "SSH",
            "remotepath": dst,
            "validate_rpath": False,
        }):
            pass

    assert e.value.errors == [
        ValidationError(
            "rsync_task_create.remotehost",
            RegexString("Failed to load .*known_hosts.*"),
            errno.EINVAL,
        ),
    ]


def test_ssh_keyscan_appends_to_existing_known_hosts(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    """Keyscanning a new host appends to a known_hosts file that has no trailing newline."""
    install_home_directory_key(localuser, ssh_credentials)
    # A comment-only file (no trailing newline) that does not match the target host
    ssh(f"echo -n '# existing comment' > {localuser['home']}/.ssh/known_hosts")
    ssh(f"chown localuser:localuser {localuser['home']}/.ssh/known_hosts")

    with task({
        "path": f"{src}/",
        "user": "localuser",
        "remotehost": "remoteuser@localhost",
        "remoteport": 22,
        "mode": "SSH",
        "remotepath": dst,
        "ssh_keyscan": True,
        "validate_rpath": False,
    }):
        pass

    known_hosts = ssh(f"cat {localuser['home']}/.ssh/known_hosts")
    assert known_hosts.startswith("# existing comment\n")
    assert "localhost" in known_hosts


def test_ssh_connection_refused(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    """A refused connection during remote path validation produces a validation error."""
    install_home_directory_key(localuser, ssh_credentials)

    with pytest.raises(ValidationErrors) as e:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "remotehost": "remoteuser@localhost",
            "remoteport": 1,
            "mode": "SSH",
            "remotepath": dst,
            "validate_rpath": True,
        }):
            pass

    assert e.value.errors == [
        ValidationError("rsync_task_create.remotehost", ANY, errno.EINVAL),
    ]


# ---------------------------------------------------------------------------
# SSH command building (task.py: build_commandline)
# ---------------------------------------------------------------------------


def test_run_with_extra_options(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    ssh(f"touch {src}/excluded_file")
    ssh(f"chown localuser:localuser {src}/excluded_file")
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": dst,
        "extra": ["--exclude", "excluded_file"],
    }) as t:
        run_task(t)

    files = ssh(f"ls -1 {dst}").split()
    assert "test" in files
    assert "excluded_file" not in files


def test_run_quiet(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": dst,
        "quiet": True,
    }) as t:
        run_task(t)

    assert ssh(f"ls -1 {dst}") == "test\n"


def test_run_pull_direction(cleanup, localuser, remoteuser, src, dst, ssh_credentials):
    ssh(f"touch {dst}/remote_file")
    ssh(f"chown remoteuser:remoteuser {dst}/remote_file")
    with task({
        "path": f"{src}/",
        "user": "localuser",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "mode": "SSH",
        "remotepath": f"{dst}/",
        "direction": "PULL",
    }) as t:
        run_task(t)

    assert "remote_file" in ssh(f"ls -1 {src}").split()


def test_run_ssh_credentials_private_key_removed(cleanup, localuser, remoteuser, src, dst):
    """If the credential's key pair loses its private key after the task is created, running it fails clearly.

    A dedicated (function-scoped) credential is used so mutating its key pair does not affect other tests.
    """
    with localhost_ssh_credentials(username="remoteuser") as c:
        with task({
            "path": f"{src}/",
            "user": "localuser",
            "ssh_credentials": c["credentials"]["id"],
            "mode": "SSH",
            "remotepath": dst,
        }) as t:
            # A key pair with only a public key is valid; this drops the private key via the API.
            call("keychaincredential.update", c["keypair"]["id"], {
                "attributes": {"public_key": c["keypair"]["attributes"]["public_key"]},
            })

            with pytest.raises(Exception, match="has no private key"):
                run_task(t)
