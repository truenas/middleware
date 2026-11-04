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


@pytest.fixture
def allow_result_serialization_fallback():
    # `conftest.init_test_environment` turns the fallback off so that tests see validation errors.
    # The tests that use this fixture cover the fallback itself.
    call("test.set_dump_result_allow_fallback", True)
    try:
        yield
    finally:
        call("test.set_dump_result_allow_fallback", False)


@contextlib.contextmanager
def wrap(id):
    yield id


@contextlib.contextmanager
def replace_datastore_field_value(datastore, filters, field, value):
    old = call("datastore.query", datastore, filters, {"get": True})[field]
    call("datastore.update", datastore, filters, {field: value})
    try:
        yield
    finally:
        call("datastore.update", datastore, filters, {field: old})


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


def test_disk_redacts_the_password_of_an_invalid_row(readonly_client, allow_result_serialization_fallback):
    with disk() as identifier:
        with replace_datastore_field_value(
            "storage.disk", [["disk_identifier", "=", identifier]], "disk_hddstandby", "BROKEN",
        ):
            result = readonly_client.call(
                "disk.query", [["identifier", "=", identifier]], {"extra": {"passwords": True}},
            )

    assert len(result) == 1
    assert result[0]["passwd"] == REDACTED


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
def iscsi_auth(tag=1, user="test", peeruser="peeruser"):
    auth = call("iscsi.auth.create", {
        "tag": tag,
        "user": user,
        "secret": "secretsecret",
        "peeruser": peeruser,
        "peersecret": "peersecretsecret",
    })
    try:
        yield auth["id"]
    finally:
        call("iscsi.auth.delete", auth["id"])


def test_iscsi_auth_redacts_secrets_of_an_invalid_row(readonly_client, allow_result_serialization_fallback):
    with iscsi_auth(tag=31, user="broken", peeruser="brokenpeer") as id_:
        with replace_datastore_field_value(
            "services.iscsitargetauthcredential",
            [["id", "=", id_]],
            "iscsi_target_auth_discovery_auth",
            "BROKEN",
        ):
            result = readonly_client.call("iscsi.auth.query", [["id", "=", id_]], {"get": True})

    assert result == {
        "id": id_,
        "tag": 31,
        "user": "broken",
        "secret": REDACTED,
        "peeruser": "brokenpeer",
        "peersecret": REDACTED,
        "discovery_auth": "BROKEN",
    }


def test_iscsi_auth_redacts_secrets_of_the_rows_around_an_invalid_one(
    readonly_client, allow_result_serialization_fallback,
):
    with iscsi_auth(tag=31, user="valid", peeruser="validpeer") as valid_id:
        with iscsi_auth(tag=32, user="broken", peeruser="brokenpeer") as broken_id:
            with replace_datastore_field_value(
                "services.iscsitargetauthcredential",
                [["id", "=", broken_id]],
                "iscsi_target_auth_discovery_auth",
                "BROKEN",
            ):
                result = readonly_client.call("iscsi.auth.query", [["id", "in", [valid_id, broken_id]]])

    assert len(result) == 2
    for auth in result:
        assert auth["secret"] == REDACTED, auth
        assert auth["peersecret"] == REDACTED, auth


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


def test_vmware_redacts_the_password_of_an_invalid_row(readonly_client, allow_result_serialization_fallback):
    with vmware() as id:
        with replace_datastore_field_value(
            "storage.vmwareplugin", [["id", "=", id]], "state", {"state": "BROKEN"},
        ):
            result = readonly_client.call("vmware.query", [["id", "=", id]])

    assert len(result) == 1
    assert result[0]["password"] == REDACTED


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


def test_system_general_redacts_the_ui_certificate_of_an_invalid_row(
    readonly_client, allow_result_serialization_fallback,
):
    with replace_datastore_field_value(
        "system.settings", [["id", "=", 1]], "stg_guix_frame_options", "BROKEN",
    ):
        result = readonly_client.call("system.general.config")

    assert result["ui_certificate"] == REDACTED
    assert result["ui_x_frame_options"] == "BROKEN"


@contextlib.contextmanager
def active_directory_with_ldap_trusted_domain():
    config = call("datastore.config", "directoryservices")
    restore = {k: config[k] for k in ("service_type", "ad_domain", "ad_enable_trusted_domains", "ad_trusted_domains")}
    call("datastore.update", "directoryservices", config["id"], {
        "service_type": "ACTIVEDIRECTORY",
        "ad_domain": "ACME.INTERNAL",
        "ad_enable_trusted_domains": True,
        "ad_trusted_domains": [{
            "idmap_backend": "LDAP",
            "name": "ACME",
            "range_low": 100000,
            "range_high": 200000,
            "ldap_base_dn": "dc=acme,dc=internal",
            "ldap_user_dn": "cn=admin,dc=acme,dc=internal",
            "ldap_user_dn_password": "canary",
            "ldap_url": "ldap://ldap.acme.internal",
        }],
    })
    try:
        yield config["id"]
    finally:
        call("datastore.update", "directoryservices", config["id"], restore)


def test_directoryservices_redacts_an_idmap_secret_of_an_invalid_row(
    readonly_client, allow_result_serialization_fallback,
):
    with active_directory_with_ldap_trusted_domain() as id_:
        with replace_datastore_field_value("directoryservices", [["id", "=", id_]], "timeout", 1):
            result = readonly_client.call("directoryservices.config")

    assert result["timeout"] == 1
    assert result["configuration"]["trusted_domains"][0]["ldap_user_dn_password"] == REDACTED


def test_fields_are_visible_if_has_write_access():
    with unprivileged_user_client(["ACCOUNT_WRITE"]) as c:
        result = c.call("user.get_instance", 1)

    assert result["unixhash"] != REDACTED


def test_fields_are_visible_for_api_key():
    with api_key() as key:
        with client(auth=None) as c:
            resp = c.call("auth.login_ex", {
                "mechanism": "API_KEY_PLAIN",
                "username": "root",
                "api_key": key,
            })
            assert resp["response_type"] == "SUCCESS"
            result = c.call("user.get_instance", 1)

    assert result["unixhash"] != REDACTED


def test_vm_display_device(readonly_client):
    with vm_device():
        result = readonly_client.call("vm.get_display_devices", 5)
        assert result[0]["attributes"]["password"] == REDACTED
