import contextlib

from middlewared.test.integration.assets.cloud_sync import credential, task, run_task
from middlewared.test.integration.assets.keychain import ssh_keypair
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, password, ssh


@contextlib.contextmanager
def root_authorized_key(public_key):
    """Add `public_key` to the root user's authorized_keys, restoring the original on exit."""
    root = call("user.query", [["username", "=", "root"]], {"get": True})
    original = root["sshpubkey"] or ""
    call("user.update", root["id"], {"sshpubkey": public_key})
    try:
        yield
    finally:
        call("user.update", root["id"], {"sshpubkey": original})


@contextlib.contextmanager
def local_sftp_credential():
    """SFTP cloud sync credential that authenticates to the local SSH server as root with a generated key."""
    with ssh_keypair() as keypair:
        with root_authorized_key(keypair["attributes"]["public_key"]):
            with credential(
                {
                    "provider": {
                        "type": "SFTP",
                        "host": "localhost",
                        "port": 22,
                        "user": "root",
                        "private_key": keypair["id"],
                    },
                }
            ) as c:
                yield c


@contextlib.contextmanager
def local_sftp_password_credential():
    """SFTP cloud sync credential that authenticates to the local SSH server as root with the root password.

    This exercises the password branch of ``SFTPRcloneRemote`` (no ``private_key``), which does not
    write or clean up a temporary key file.
    """
    with credential(
        {
            "provider": {
                "type": "SFTP",
                "host": "localhost",
                "port": 22,
                "user": "root",
                "pass": password(),
            },
        }
    ) as c:
        yield c


def test_sftp_push_with_password():
    with dataset("cloudsync_sftp_local") as local_dataset:
        ssh(f"mkdir /mnt/{local_dataset}/dir")
        ssh(f"touch /mnt/{local_dataset}/dir/file")

        with dataset("cloudsync_sftp_remote") as remote_dataset:
            with local_sftp_password_credential() as c:
                with task(
                    {
                        "direction": "PUSH",
                        "transfer_mode": "COPY",
                        "path": f"/mnt/{local_dataset}",
                        "credentials": c["id"],
                        "attributes": {
                            "folder": f"/mnt/{remote_dataset}",
                        },
                    }
                ) as t:
                    run_task(t)

                    assert ssh(f"ls /mnt/{remote_dataset}") == "dir\n"
                    assert ssh(f"ls /mnt/{remote_dataset}/dir") == "file\n"


def test_sftp_list_directory_with_password():
    with dataset("cloudsync_sftp_remote") as remote_dataset:
        ssh(f"touch /mnt/{remote_dataset}/file")

        with local_sftp_password_credential() as c:
            listing = call(
                "cloudsync.list_directory",
                {
                    "credentials": c["id"],
                    "attributes": {
                        "folder": f"/mnt/{remote_dataset}",
                    },
                },
            )

            assert [item["Name"] for item in listing] == ["file"]


def test_sftp_push():
    with dataset("cloudsync_sftp_local") as local_dataset:
        ssh(f"mkdir /mnt/{local_dataset}/dir")
        ssh(f"touch /mnt/{local_dataset}/dir/file")

        with dataset("cloudsync_sftp_remote") as remote_dataset:
            with local_sftp_credential() as c:
                with task(
                    {
                        "direction": "PUSH",
                        "transfer_mode": "COPY",
                        "path": f"/mnt/{local_dataset}",
                        "credentials": c["id"],
                        "attributes": {
                            "folder": f"/mnt/{remote_dataset}",
                        },
                    }
                ) as t:
                    run_task(t)

                    assert ssh(f"ls /mnt/{remote_dataset}") == "dir\n"
                    assert ssh(f"ls /mnt/{remote_dataset}/dir") == "file\n"


def test_sftp_pull():
    with dataset("cloudsync_sftp_remote") as remote_dataset:
        ssh(f"touch /mnt/{remote_dataset}/file")

        with dataset("cloudsync_sftp_local") as local_dataset:
            with local_sftp_credential() as c:
                with task(
                    {
                        "direction": "PULL",
                        "transfer_mode": "COPY",
                        "path": f"/mnt/{local_dataset}",
                        "credentials": c["id"],
                        "attributes": {
                            "folder": f"/mnt/{remote_dataset}",
                        },
                    }
                ) as t:
                    run_task(t)

                    assert ssh(f"ls /mnt/{local_dataset}") == "file\n"


def test_sftp_list_directory():
    with dataset("cloudsync_sftp_remote") as remote_dataset:
        ssh(f"touch /mnt/{remote_dataset}/file")

        with local_sftp_credential() as c:
            listing = call(
                "cloudsync.list_directory",
                {
                    "credentials": c["id"],
                    "attributes": {
                        "folder": f"/mnt/{remote_dataset}",
                    },
                },
            )

            assert [item["Name"] for item in listing] == ["file"]
