import io
import json
import os
import subprocess
import tarfile
import tempfile

import pytest
import requests

from middlewared.test.integration.assets.keychain import ssh_keypair
from middlewared.test.integration.utils import call, client, host, ssh, url


@pytest.fixture(scope="module")
def admin():
    assert call("user.query", [["uid", "=", 1000]]) == []
    assert call("user.query", [["username", "=", "admin"]]) == []

    root_backup = call("datastore.query", "account.bsdusers", [["bsdusr_username", "=", "root"]], {"get": True})
    root_backup["bsdusr_group"] = root_backup["bsdusr_group"]["id"]
    root_id = root_backup.pop("id")
    # Connect before removing root password
    with client() as c:
        stdin = json.dumps({"username": "admin", "password": "admin"})
        ssh(f"echo '{stdin}' | truenas-set-authentication-method.py")
        # Quickly restore root password before anyone notices
        c.call("datastore.update", "account.bsdusers", root_id, root_backup)
        c.call("etc.generate", "user")

    admin = call("user.query", [["username", "=", "admin"]], {"get": True})
    try:
        yield admin
    finally:
        call("user.delete", admin["id"])


def test_installer_admin_has_local_administrator_privilege(admin):
    with client(auth=("admin", "admin")) as c:
        c.call("system.info")


def test_can_set_admin_authorized_key(admin):
    with ssh_keypair() as keypair:
        call("user.update", admin["id"], {
            "sshpubkey": keypair["attributes"]["public_key"],
        })
        try:
            with tempfile.NamedTemporaryFile("w") as f:
                os.chmod(f.name, 0o600)
                f.write(keypair["attributes"]["private_key"])
                f.flush()

                subprocess.run([
                    "ssh",
                    "-i", f.name,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "VerifyHostKeyDNS=no",
                    f"admin@{host()}",
                    "uptime",
                ], capture_output=True, check=True, timeout=30)

                job_id, path = call("core.download", "config.save", [{"root_authorized_keys": True}], "config.tar")
                r = requests.get(f"{url()}{path}")
                r.raise_for_status()
                tar_io = io.BytesIO(r.content)
                with tarfile.TarFile(fileobj=tar_io) as tar:
                    member = tar.getmember("admin_authorized_keys")
                    assert member.uid == 1000
                    assert member.gid == 1000
                    assert member.uname == "admin"
                    assert member.gname == "admin"
                    assert tar.extractfile(member).read().decode() == keypair["attributes"]["public_key"]
        finally:
            call("user.update", admin["id"], {
                "sshpubkey": "",
            })
