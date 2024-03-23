import io
import os
import subprocess
import tarfile
import tempfile

import pytest
import requests

from middlewared.test.integration.assets.account import root_with_password_disabled
from middlewared.test.integration.assets.keychain import ssh_keypair
from middlewared.test.integration.utils import call, client, host, mock, url

pytestmark = pytest.mark.accounts


@pytest.fixture(scope="module")
def admin():
    assert call("user.query", [["uid", "=", 950]]) == []
    assert call("user.query", [["username", "=", "admin"]]) == []

    with root_with_password_disabled() as context:
        context.client.call("datastore.update", "account.bsdusers", context.root_id, {"bsdusr_unixhash": "*"})
        context.client.call("user.setup_local_administrator", "admin", "admin")
        call("system.info", client_kwargs=dict(auth=("admin", "admin")))
        # Quickly restore root password before anyone notices
        context.client.call("datastore.update", "account.bsdusers", context.root_id, context.root_backup)
        context.client.call("etc.generate", "user")

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
                    assert member.uid == 950
                    assert member.gid == 950
                    assert member.uname == "admin"
                    assert member.gname == "admin"
                    assert tar.extractfile(member).read().decode() == keypair["attributes"]["public_key"]
        finally:
            call("user.update", admin["id"], {
                "sshpubkey": "",
            })


def test_admin_user_alert(admin):
    with mock("user.get_user_obj", args=[{"uid": 950}], return_value={
        "pw_name": "root", "pw_uid": 0, "pw_gid": 0, "pw_gecos": "root", "pw_dir": "/root", "pw_shell": "/usr/bin/zsh"
    }):
        alerts = call("alert.run_source", "AdminUser")
        assert len(alerts) == 1
        assert alerts[0]["klass"] == "AdminUserIsOverridden"


def test_admin_user_no_alert(admin):
    assert not call("alert.run_source", "AdminUser")
