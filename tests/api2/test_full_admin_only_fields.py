"""End-to-end coverage for the `FullAdmin` field marker (NAS-142160).

A marked field is one whose value middleware passes through unvalidated to a root command line or to a
privileged daemon's configuration, so a caller who lacks `FULL_ADMIN` may not change it -- but must still be
able to edit everything else on the same endpoint, including writing the marked field's current value back
unchanged, which is what read-modify-write clients do.

The comparison logic itself is covered by `middlewared.pytest.unit.api.base.test_full_admin`. What is proven
here is that each of the four ways a method reaches the check is actually wired up:

* `ConfigService.update`   -- `ssh`, `ftp`, `snmp`, `ups`, `system.advanced`
* `CRUDService.create`     -- `cloudsync.create`
* `CRUDService.update`     -- `cloudsync.update`
* an explicit call         -- `cloudsync.list_directory`, `cloudsync.sync_onetime`
"""

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.cloud_sync import local_ftp_credential, local_ftp_task
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

DENIED = "restricted to users with full administrative privileges"

# `namespace`, the marked field, and a value that differs from whatever the field currently holds.
CONFIG_SERVICES = [
    ("ssh", "options", "PermitRootLogin yes"),
    ("ftp", "options", "RootLogin on"),
    ("snmp", "options", 'extend test /bin/sh -c "id"'),
    ("ups", "shutdowncmd", "/bin/sh -c id"),
    ("ups", "options", "user = root"),
    ("ups", "optionsupsd", "LISTEN 0.0.0.0 3493"),
    ("ups", "extrausers", "[hax]\n\tpassword = hax\n\tupsmon master"),
    ("system.advanced", "kernel_extra_options", "init=/bin/sh"),
]

CONFIG_FIELDS = [(namespace, field) for namespace, field, _ in CONFIG_SERVICES]

CONFIG_ROLES = ["SSH_WRITE", "SHARING_FTP_WRITE", "SYSTEM_GENERAL_WRITE", "SYSTEM_ADVANCED_WRITE"]


def assert_denied(ve, attribute):
    assert any(error.attribute == attribute and DENIED in error.errmsg for error in ve.value.errors), ve.value.errors


@pytest.fixture(scope="module")
def config_client():
    with unprivileged_user_client(CONFIG_ROLES) as c:
        yield c


@pytest.fixture(scope="module")
def cloud_client():
    with unprivileged_user_client(["CLOUD_SYNC_WRITE"]) as c:
        yield c


@pytest.fixture(scope="module")
def cloudsync_template():
    with local_ftp_credential() as credential:
        with dataset("full_admin_fields") as local_dataset:
            yield {
                "path": f"/mnt/{local_dataset}",
                "credentials": credential["id"],
                "direction": "PUSH",
                "transfer_mode": "COPY",
                "attributes": {"folder": ""},
            }


class TestConfigServiceUpdate:
    @pytest.mark.parametrize("namespace,field,value", CONFIG_SERVICES)
    def test_changing_is_denied(self, config_client, namespace, field, value):
        assert call(f"{namespace}.config")[field] != value, "test value must differ from the current one"

        with pytest.raises(ValidationErrors) as ve:
            config_client.call(f"{namespace}.update", {field: value})

        assert_denied(ve, f"data.{field}" if namespace != "snmp" else f"snmp_update.{field}")

    @pytest.mark.parametrize("namespace,field", CONFIG_FIELDS)
    def test_writing_the_current_value_back_is_allowed(self, config_client, namespace, field):
        current = call(f"{namespace}.config")[field]

        assert config_client.call(f"{namespace}.update", {field: current})[field] == current

    def test_an_unrelated_field_is_still_editable(self, config_client):
        """The point of comparing against the stored value: everything else on the endpoint keeps working."""
        original = call("ssh.config")["tcpport"]
        try:
            assert config_client.call("ssh.update", {"tcpport": original + 1})["tcpport"] == original + 1
        finally:
            call("ssh.update", {"tcpport": original})

    def test_a_full_admin_may_still_change_it(self):
        original = call("ups.config")["shutdowncmd"]
        try:
            assert call("ups.update", {"shutdowncmd": "/bin/true"})["shutdowncmd"] == "/bin/true"
        finally:
            call("ups.update", {"shutdowncmd": original})


class TestCrudCreate:
    def test_setting_on_create_is_denied(self, cloud_client, cloudsync_template):
        with pytest.raises(ValidationErrors) as ve:
            cloud_client.call("cloudsync.create", {**cloudsync_template, "args": "--rc --rc-no-auth"})

        assert_denied(ve, "cloud_sync_create.args")

    def test_the_default_on_create_is_allowed(self, cloud_client, cloudsync_template):
        task = cloud_client.call("cloudsync.create", {**cloudsync_template, "args": ""})
        try:
            assert task["args"] == ""
        finally:
            call("cloudsync.delete", task["id"])


class TestCrudUpdate:
    def test_changing_is_denied(self, cloud_client):
        with local_ftp_task() as task:
            with pytest.raises(ValidationErrors) as ve:
                cloud_client.call("cloudsync.update", task["id"], {"args": "--rc --rc-no-auth"})

            assert_denied(ve, "cloud_sync_update.args")

    def test_writing_the_current_value_back_is_allowed(self, cloud_client):
        """A task created with `args` stays editable by someone who may not change `args`."""
        with local_ftp_task({"args": "--stats 5s"}) as task:
            updated = cloud_client.call(
                "cloudsync.update",
                task["id"],
                {
                    "args": "--stats 5s",
                    "description": "edited by an unprivileged user",
                },
            )

            assert updated["description"] == "edited by an unprivileged user"
            assert updated["args"] == "--stats 5s"


class TestExplicitlyCheckedMethods:
    """`cloudsync.list_directory` and `cloudsync.sync_onetime` bypass the CRUD wrappers and check themselves."""

    def test_list_directory_is_denied(self, cloud_client, cloudsync_template):
        with pytest.raises(ValidationErrors) as ve:
            cloud_client.call(
                "cloudsync.list_directory",
                {
                    "credentials": cloudsync_template["credentials"],
                    "attributes": {"folder": ""},
                    "args": "--rc --rc-no-auth",
                },
            )

        assert_denied(ve, "cloud_sync_ls.args")

    def test_sync_onetime_is_denied(self, cloud_client, cloudsync_template):
        with pytest.raises(ValidationErrors) as ve:
            cloud_client.call(
                "cloudsync.sync_onetime",
                {**cloudsync_template, "args": "--rc --rc-no-auth"},
                job=True,
            )

        assert_denied(ve, "cloud_sync_sync_onetime.args")
