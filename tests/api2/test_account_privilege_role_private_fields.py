import contextlib

import pytest

from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.cloud_backup import task as cloud_backup_task
from middlewared.test.integration.assets.cloud_sync import local_ftp_credential, local_ftp_task
from middlewared.test.integration.assets.datastore import row
from middlewared.test.integration.assets.keychain import ssh_keypair
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

REDACTED = "********"


@pytest.fixture(scope="module")
def readonly_client():
    with unprivileged_user_client(["READONLY"]) as c:
        yield c


@contextlib.contextmanager
def wrap(id):
    yield id


@contextlib.contextmanager
def cloudbackup():
    with local_ftp_credential() as credential:
        with dataset("cloud_backup") as local_dataset:
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
            "authenticator": "cloudflare",
            "name": "test",
            "attributes": {
                "api_key": "key",
                "api_token": "token",
            },
        },
    ) as id:
        yield id


@contextlib.contextmanager
def idmap():
    with row(
        "directoryservice.idmap_domain",
        {
            "name": "test",
            "dns_domain_name": "test",
            "range_low": 1000,
            "range_high": 1001,
            "idmap_backend": "LDAP",
            "options": {
                "ldap_base_dn": "cn=BASEDN",
                "ldap_user_dn": "cn=USERDN",
                "ldap_url": "ldap://127.0.0.1",
                "ldap_user_dn_password": "password"
            },
        },
        {"prefix": "idmap_domain_"},
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
    ("cloud_backup", cloudbackup, {}, ["credentials.attributes", "password"]),
    ("cloudsync.credentials", cloudsync_credential, {}, ["attributes"]),
    ("cloudsync", cloudsync, {}, ["credentials.attributes", "encryption_password"]),
    ("disk", disk, {"extra": {"passwords": True}}, ["passwd"]),
    ("idmap", idmap, {}, ["options.ldap_user_dn_password"]),
    ("iscsi.auth", iscsi_auth, {}, ["secret", "peersecret"]),
    ("keychaincredential", keychaincredential, {}, ["attributes"]),
    ("user", 1, {}, ["unixhash", "smbhash"]),
    ("vmware", vmware, {}, ["password"]),
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
    ("ldap", ["bindpw"]),
    ("mail", ["pass", "oauth"]),
    ("snmp", ["v3_password", "v3_privpassphrase"]),
    ("truecommand", ["api_key"]),
))
def test_config(readonly_client, service, redacted_fields):
    result = readonly_client.call(f"{service}.config")

    for k in redacted_fields:
        assert result[k] == REDACTED
