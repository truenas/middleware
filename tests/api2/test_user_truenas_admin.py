import io
import os
import subprocess
import tarfile
import tempfile

import pytest
from functions import http_get

from middlewared.test.integration.assets.account import root_with_password_disabled
from middlewared.test.integration.assets.keychain import ssh_keypair
from middlewared.test.integration.utils import call, client, host, mock, url


@pytest.fixture(scope="module")
def truenas_admin():
    assert call("user.query", [["uid", "=", 950]]) == []
    assert call("user.query", [["username", "=", "truenas_admin"]]) == []

    with root_with_password_disabled() as context:
        context.client.call("datastore.update", "account.bsdusers", context.root_id, {"bsdusr_unixhash": "*"})
        context.client.call("user.setup_local_administrator", "truenas_admin", "password")
        call("system.info", client_kwargs=dict(auth=("truenas_admin", "password")))
        # Quickly restore root password before anyone notices
        context.client.call("datastore.update", "account.bsdusers", context.root_id, context.root_backup)
        context.client.call("etc.generate", "user")

        truenas_admin = call("user.query", [["username", "=", "truenas_admin"]], {"get": True})
        try:
            yield truenas_admin
        finally:
            call("datastore.delete", "account.bsdusers", truenas_admin["id"])
            call("etc.generate", "user")


def test_installer_admin_has_local_administrator_privilege(truenas_admin):
    with client(auth=("truenas_admin", "password")) as c:
        c.call("system.info")


def test_can_set_admin_authorized_key(truenas_admin):
    with ssh_keypair() as keypair:
        call("user.update", truenas_admin["id"], {
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
                    f"truenas_admin@{host().ip}",
                    "uptime",
                ], capture_output=True, check=True, timeout=30)

                job_id, path = call("core.download", "config.save", [{"root_authorized_keys": True}], "config.tar")
                r = http_get(f"{url()}{path}")
                r.raise_for_status()
                tar_io = io.BytesIO(r.content)
                with tarfile.TarFile(fileobj=tar_io) as tar:
                    member = tar.getmember("truenas_admin_authorized_keys")
                    assert member.uid == 950
                    assert member.gid == 950
                    assert member.uname == "truenas_admin"
                    assert member.gname == "truenas_admin"
                    assert tar.extractfile(member).read().decode() == keypair["attributes"]["public_key"]
        finally:
            call("user.update", truenas_admin["id"], {
                "sshpubkey": "",
            })


def test_admin_user_alert(truenas_admin):
    with mock("user.get_user_obj", args=[{"uid": 950}], return_value={
        "pw_name": "root", "pw_uid": 0, "pw_gid": 0, "pw_gecos": "root", "pw_dir": "/root", "pw_shell": "/usr/bin/zsh"
    }):
        alerts = call("alert.run_source", "AdminUser")
        assert len(alerts) == 1
        assert alerts[0]["klass"] == "AdminUserIsOverridden"


def test_admin_user_no_alert(truenas_admin):
    assert not call("alert.run_source", "AdminUser")
