import contextlib

import pytest

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.assets.cloud_backup import task as cloud_backup_task
from middlewared.test.integration.assets.cloud_sync import local_ftp_credential, local_ftp_task
from middlewared.test.integration.assets.datastore import row
from middlewared.test.integration.assets.keychain import ssh_keypair
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, client, mock

REDACTED = "********"


@pytest.fixture(scope="module")
def readonly_client():
    with unprivileged_user_client(["READONLY_ADMIN"]) as c:
        yield c


@contextlib.contextmanager
def wrap(id):
    yield id


@contextlib.contextmanager
def cloudbackup():
    with local_ftp_credential() as credential:
        with dataset("cloud_backup") as local_dataset:
            with mock("cloud_backup.ensure_initialized", return_value=None):
                with cloud_backup_task({
                    "path": f"/mnt/{local_dataset}",
                    "credentials": credential["id"],
                    "attributes": {
                        "folder": "",
                    },
                    "password": "test",
                }) as task:
                    yield task["id"]


@contextlib.contextmanager
def cloudsync_credential():
    with local_ftp_credential() as credential:
        yield credential["id"]


@contextlib.contextmanager
def cloudsync():
    with local_ftp_task() as task:
        yield task["id"]


@contextlib.contextmanager
def disk():
    disks = call("disk.query")
    yield disks[0]["identifier"]


@contextlib.contextmanager
def dns_authenticator():
    with row(
        "system.acmednsauthenticator",
        {
            "name": "test",
            "attributes": {
                "authenticator": "cloudflare",
                "cloudflare_email": "test@gmail.com",
                "api_key": "key",
                "api_token": "token",
            },
        },
    ) as id:
        yield id


@contextlib.contextmanager
def vm_device():
    with row(
        "vm.vm",
        {
            "id": 5,
            "name": "",
            "memory": 225
        }):
        with row(
            "vm.device",
            {
                "id": 7,
                "vm": 5,
                "attributes": {
                    "dtype": "DISPLAY",
                    "bind": "127.0.0.1",
                    "port": 5900,
                    "web_port": 5901,
                    "password": "pass",
                }
            }
        ) as id:
            yield id


@contextlib.contextmanager
def iscsi_auth():
    auth = call("iscsi.auth.create", {
        "tag": 1,
        "user": "test",
        "secret": "secretsecret",
        "peeruser": "peeruser",
        "peersecret": "peersecretsecret",
    })
    try:
        yield auth["id"]
    finally:
        call("iscsi.auth.delete", auth["id"])


@contextlib.contextmanager
def keychaincredential():
    with ssh_keypair() as k:
        yield k["id"]


@contextlib.contextmanager
def vmware():
    with row(
        "storage.vmwareplugin",
        {
            "password": "password",
        },
    ) as id:
        yield id


@pytest.mark.parametrize("how", ["multiple", "single", "get_instance"])
@pytest.mark.parametrize("service,id,options,redacted_fields", (
    ("acme.dns.authenticator", dns_authenticator, {}, ["attributes"]),
    ("certificate", 1, {}, ["privatekey"]),
    ("cloud_backup", cloudbackup, {}, ["credentials.provider.pass", "password"]),
    ("cloudsync.credentials", cloudsync_credential, {}, ["provider.pass"]),
    ("cloudsync", cloudsync, {}, ["credentials.provider.pass", "encryption_password"]),
    ("disk", disk, {"extra": {"passwords": True}}, ["passwd"]),
    ("iscsi.auth", iscsi_auth, {}, ["secret", "peersecret"]),
    ("keychaincredential", keychaincredential, {}, ["attributes"]),
    ("user", 1, {}, ["unixhash", "smbhash"]),
    ("vmware", vmware, {}, ["password"]),
    ("vm.device", vm_device, {}, ["attributes.password"]),
))
def test_crud(readonly_client, how, service, id, options, redacted_fields):
    identifier = "id" if service != "disk" else "identifier"

    with (id() if callable(id) else wrap(id)) as id:
        if how == "multiple":
            result = readonly_client.call(f"{service}.query", [[identifier, "=", id]], options)[0]
        elif how == "single":
            result = readonly_client.call(f"{service}.query", [[identifier, "=", id]], {**options, "get": True})
        elif how == "get_instance":
            result = readonly_client.call(f"{service}.get_instance", id, options)
        else:
            assert False

        for k in redacted_fields:
            obj = result
            for path in k.split("."):
                obj = obj[path]

            assert obj == REDACTED, (k, obj, REDACTED)


@pytest.mark.parametrize("service,redacted_fields", (
    ("system.general", ["ui_certificate"]),
    ("mail", ["pass", "oauth"]),
    ("snmp", ["v3_password", "v3_privpassphrase"]),
    ("truecommand", ["api_key"]),
))
def test_config(readonly_client, service, redacted_fields):
    result = readonly_client.call(f"{service}.config")

    for k in redacted_fields:
        assert result[k] == REDACTED


def test_fields_are_visible_if_has_write_access():
    with unprivileged_user_client(["ACCOUNT_WRITE"]) as c:
        result = c.call("user.get_instance", 1)

    assert result["unixhash"] != REDACTED


def test_fields_are_visible_for_api_key():
    with api_key() as key:
        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", key)
            result = c.call("user.get_instance", 1)

    assert result["unixhash"] != REDACTED


def test_vm_display_device(readonly_client):
    with vm_device():
        result = readonly_client.call("vm.get_display_devices", 5)
        assert result[0]["attributes"]["password"] == REDACTED
