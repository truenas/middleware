import contextlib
import time

import pytest

from middlewared.test.integration.assets.crypto import generate_self_signed_pem, imported_certificate
from middlewared.test.integration.assets.kmip import KMIP_HOST, KMIP_PORT, kmip_enabled, kmip_server
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from truenas_api_client.exc import ClientException, ValidationErrors

# A port nothing is listening on, used to exercise the "server unreachable" paths.
DEAD_PORT = 5699
# Second KMIP server used by the `change_server` migration test.
SECOND_PORT = 5697
SED_PASSWORD = "kmip-sed-password"
# Configuration that returns KMIP to its pristine, disabled state. `force_clear` drops
# any key that never made it to the KMIP server so that the update is not rejected.
KMIP_RESET = {
    "enabled": False,
    "server": None,
    "port": KMIP_PORT,
    "certificate": None,
    "certificate_authority": None,
    "manage_zfs_keys": False,
    "manage_sed_disks": False,
    "force_clear": True,
    "validate": False,
}


@pytest.fixture(scope="module")
def kmip_server_pem():
    """PEM material shared by every fake KMIP server and by the middleware's KMIP client."""
    return generate_self_signed_pem(common_name=KMIP_HOST)


@pytest.fixture(scope="module")
def kmip_certificate(kmip_server_pem):
    """Run the fake KMIP server and import its certificate into the middleware store.

    PyKMIP's server slows down markedly once it has been asked to operate on objects it
    does not know about, which the error-path tests at the bottom of this module do
    deliberately. Those tests are therefore kept last, so the ones that need a healthy
    server run against a freshly started one.
    """
    cert_pem, key_pem = kmip_server_pem
    # The certificate cannot be deleted while the KMIP service still references it, so
    # the configuration is reset both before and after, the former in case an earlier
    # (failed) run left KMIP configured.
    call("kmip.update", KMIP_RESET, job=True)
    with kmip_server(certificate=kmip_server_pem):
        with imported_certificate("kmip_test_cert", cert_pem, key_pem) as cert:
            try:
                yield cert
            finally:
                call("kmip.update", KMIP_RESET, job=True)


@pytest.fixture(scope="module")
def unrelated_certificate():
    """A certificate that is unrelated to the KMIP server, used for negative validation."""
    with imported_certificate("kmip_unrelated_cert") as cert:
        yield cert


@pytest.fixture
def encrypted_dataset():
    """A key-encrypted dataset whose key lives in the ``storage.encrypteddataset`` table."""
    with dataset(
        "kmip_encrypted",
        {
            "encryption": True,
            "inherit_encryption": False,
            "encryption_options": {"generate_key": True},
        },
    ) as ds:
        yield ds


def wait_for(condition, timeout=60):
    """Poll ``condition`` until it returns a truthy value and return it.

    ``kmip.sync_keys`` starts the per-key-type sync jobs without waiting for them, so
    the effect of a ``kmip.update`` only becomes visible some time after it returns.
    """
    deadline = time.monotonic() + timeout
    while True:
        result = condition()
        if result:
            return result
        assert time.monotonic() < deadline, "Timed out waiting for the KMIP sync to complete"
        time.sleep(1)


def encrypted_dataset_row(name):
    return call("datastore.query", "storage.encrypteddataset", [["name", "=", name]], {"get": True})


def set_encrypted_dataset(name, data):
    call("datastore.update", "storage.encrypteddataset", encrypted_dataset_row(name)["id"], data)


def disk_row(identifier):
    return call(
        "datastore.query", "storage.disk", [["identifier", "=", identifier]], {"prefix": "disk_", "get": True}
    )


def advanced_row():
    return call("datastore.config", "system.advanced", {"prefix": "adv_"})


@contextlib.contextmanager
def global_sed_password(password=SED_PASSWORD):
    """Set (and afterwards clear) the global SED password stored in ``system.advanced``."""
    call("system.advanced.update", {"sed_passwd": password})
    try:
        yield password
    finally:
        call("system.advanced.update", {"sed_passwd": ""})


@contextlib.contextmanager
def sed_disk_password(password=SED_PASSWORD):
    """Write a SED password directly into a ``storage.disk`` row and restore it afterwards.

    The middleware only ever populates ``disk_passwd`` for real SED drives, which the test
    machines do not have, so the row is seeded through the datastore instead.
    """
    disks = call("datastore.query", "storage.disk", [], {"prefix": "disk_"})
    if not disks:
        pytest.skip("No disks in the storage.disk table")

    disk = disks[0]
    call("datastore.update", "storage.disk", disk["identifier"], {"passwd": password}, {"prefix": "disk_"})
    try:
        yield disk["identifier"]
    finally:
        call(
            "datastore.update", "storage.disk", disk["identifier"],
            {"passwd": "", "kmip_uid": None}, {"prefix": "disk_"},
        )
        call("kmip.reset_sed_disk_password", disk["identifier"], None)


def test_kmip_config_defaults():
    config = call("kmip.config")
    assert config["enabled"] is False
    assert config["port"] == 5696
    assert config["ssl_version"] == "PROTOCOL_TLSv1_2"
    assert config["manage_zfs_keys"] is False
    assert config["manage_sed_disks"] is False


def test_kmip_enable_connects_to_server(kmip_certificate):
    with kmip_enabled(kmip_certificate["id"]):
        config = call("kmip.config")
        assert config["enabled"] is True
        assert config["server"] == KMIP_HOST
        assert config["port"] == KMIP_PORT
        assert config["certificate"] == kmip_certificate["id"]
        assert config["certificate_authority"] == kmip_certificate["id"]
        # No datasets/disks are managed, so nothing should be pending sync.
        assert call("kmip.kmip_sync_pending") is False

    # After the context manager exits KMIP should be disabled again.
    assert call("kmip.config")["enabled"] is False


def test_kmip_enable_unreachable_server_fails(kmip_certificate):
    # Nothing is listening on this port, so the pre-save connection test must fail.
    with pytest.raises(ValidationErrors) as ve:
        with kmip_enabled(kmip_certificate["id"], port=DEAD_PORT):
            pass

    assert any("kmip_update.server" == error.attribute for error in ve.value.errors), ve.value.errors
    assert call("kmip.config")["enabled"] is False


def test_kmip_enable_without_server_fails(kmip_certificate):
    with pytest.raises(ValidationErrors) as ve:
        with kmip_enabled(kmip_certificate["id"], server=None, validate=False):
            pass

    assert any("kmip_update.server" == error.attribute for error in ve.value.errors), ve.value.errors


def test_kmip_enable_with_invalid_certificate_fails(kmip_certificate):
    with pytest.raises(ValidationErrors) as ve:
        with kmip_enabled(kmip_certificate["id"], certificate=None, validate=False):
            pass

    assert any("kmip_update.certificate" == error.attribute for error in ve.value.errors), ve.value.errors


def test_kmip_enable_without_certificate_authority_fails(kmip_certificate):
    with pytest.raises(ValidationErrors) as ve:
        with kmip_enabled(kmip_certificate["id"], certificate_authority=None, validate=False):
            pass

    assert any(
        "kmip_update.certificate_authority" == error.attribute for error in ve.value.errors
    ), ve.value.errors


def test_kmip_certificate_not_signed_by_authority_fails(kmip_certificate, unrelated_certificate):
    # The certificate chain cannot be verified against an unrelated certificate authority.
    with pytest.raises(ValidationErrors) as ve:
        with kmip_enabled(
            kmip_certificate["id"], certificate_authority=unrelated_certificate["id"], validate=False,
        ):
            pass

    assert any(
        "kmip_update.certificate_authority" == error.attribute for error in ve.value.errors
    ), ve.value.errors


def test_kmip_invalid_port_fails(kmip_certificate):
    # Port 80 is already claimed by the web UI.
    with pytest.raises(ValidationErrors) as ve:
        with kmip_enabled(kmip_certificate["id"], port=80, validate=False):
            pass

    assert any("kmip_update.port" == error.attribute for error in ve.value.errors), ve.value.errors


def test_kmip_change_server_validation(kmip_certificate):
    with kmip_enabled(kmip_certificate["id"]):
        # `change_server` requires a server different from the currently configured one.
        with pytest.raises(ValidationErrors) as ve:
            call("kmip.update", {"change_server": True, "server": KMIP_HOST, "validate": False}, job=True)

        assert any("kmip_update.change_server" == error.attribute for error in ve.value.errors), ve.value.errors

        # `change_server` is meaningless while KMIP is disabled.
        with pytest.raises(ValidationErrors) as ve:
            call(
                "kmip.update",
                {"change_server": True, "enabled": False, "server": "localhost", "validate": False},
                job=True,
            )

        assert any("kmip_update.enabled" == error.attribute for error in ve.value.errors), ve.value.errors


def test_kmip_zfs_keys_pushed_and_pulled(kmip_certificate, encrypted_dataset):
    row = encrypted_dataset_row(encrypted_dataset)
    key = row["encryption_key"]
    assert key
    assert row["kmip_uid"] is None

    with kmip_enabled(kmip_certificate["id"], manage_zfs_keys=True):
        # The key must have been handed over to the KMIP server.
        row = wait_for(lambda: encrypted_dataset_row(encrypted_dataset)["kmip_uid"] and
                       encrypted_dataset_row(encrypted_dataset))
        assert row["encryption_key"] is None

        # Turning `manage_zfs_keys` off pulls the key back from the KMIP server.
        call("kmip.update", {"manage_zfs_keys": False}, job=True)

        row = wait_for(lambda: encrypted_dataset_row(encrypted_dataset)["encryption_key"] and
                       encrypted_dataset_row(encrypted_dataset))
        assert row["encryption_key"] == key
        assert row["kmip_uid"] is None

    wait_for(lambda: call("kmip.kmip_sync_pending") is False)


def test_kmip_sed_keys_pushed_and_pulled(kmip_certificate):
    with global_sed_password() as password, sed_disk_password() as disk_id:
        with kmip_enabled(kmip_certificate["id"], manage_sed_disks=True):
            adv = wait_for(lambda: (r := advanced_row())["kmip_uid"] and r)
            assert adv["sed_passwd"] == ""
            assert call("kmip.sed_global_password") == password

            disk = wait_for(lambda: (r := disk_row(disk_id))["kmip_uid"] and r)
            assert disk["passwd"] == ""
            assert call("kmip.retrieve_sed_disks_keys")[disk_id] == password

            # Turning `manage_sed_disks` off pulls the keys back into the database.
            call("kmip.update", {"manage_sed_disks": False}, job=True)

            adv = wait_for(lambda: (r := advanced_row())["sed_passwd"] and r)
            assert adv["sed_passwd"] == password
            assert adv["kmip_uid"] is None

            disk = disk_row(disk_id)
            assert disk["passwd"] == password
            assert disk["kmip_uid"] is None

    wait_for(lambda: call("kmip.kmip_sync_pending") is False)


def test_kmip_global_sed_password_only(kmip_certificate):
    # No disk password is set, so the global password is the only thing pending sync.
    with global_sed_password() as password:
        with kmip_enabled(kmip_certificate["id"], manage_sed_disks=True):
            wait_for(lambda: advanced_row()["kmip_uid"])
            assert advanced_row()["sed_passwd"] == ""

            call("kmip.update", {"manage_sed_disks": False}, job=True)
            wait_for(lambda: advanced_row()["sed_passwd"] == password)
            assert advanced_row()["kmip_uid"] is None

    wait_for(lambda: call("kmip.kmip_sync_pending") is False)


def test_kmip_zfs_keys_migrated_to_new_server(kmip_certificate, kmip_server_pem, encrypted_dataset):
    key = encrypted_dataset_row(encrypted_dataset)["encryption_key"]

    with kmip_enabled(kmip_certificate["id"], manage_zfs_keys=True):
        first_uid = wait_for(lambda: encrypted_dataset_row(encrypted_dataset)["kmip_uid"])

        # `localhost` resolves to the same address, but is a distinct value for the
        # `change_server` check, which refuses a migration to the very same server.
        with kmip_server(port=SECOND_PORT, certificate=kmip_server_pem):
            call(
                "kmip.update",
                {"change_server": True, "server": "localhost", "port": SECOND_PORT},
                job=True,
            )

            # The key was pulled from the old server and re-registered on the new one.
            row = wait_for(
                lambda: (r := encrypted_dataset_row(encrypted_dataset))["kmip_uid"] not in (None, first_uid) and r
            )
            assert row["encryption_key"] is None

            # Bring the key back into the database before the second server goes away.
            call("kmip.update", {"manage_zfs_keys": False}, job=True)
            wait_for(lambda: encrypted_dataset_row(encrypted_dataset)["encryption_key"] == key)


def test_kmip_zfs_key_resynced_from_server(kmip_certificate, encrypted_dataset):
    key = encrypted_dataset_row(encrypted_dataset)["encryption_key"]

    with kmip_enabled(kmip_certificate["id"], manage_zfs_keys=True):
        uid = wait_for(lambda: encrypted_dataset_row(encrypted_dataset)["kmip_uid"])

        # A second sync finds the key on the KMIP server rather than in the database and
        # only refreshes the in-memory copy, leaving the stored UID untouched.
        call("kmip.sync_zfs_keys", job=True)
        assert encrypted_dataset_row(encrypted_dataset)["kmip_uid"] == uid

        # Loading the keys on boot fetches them back from the KMIP server.
        call("kmip.update_memory_keys", {"zfs": {}})
        call("kmip.initialize_keys", job=True)
        assert call("kmip.retrieve_zfs_keys")[encrypted_dataset] == key

        # A dataset that carries both a database key and a (stale) KMIP UID has the old
        # object revoked and destroyed before the key is registered again.
        set_encrypted_dataset(encrypted_dataset, {"encryption_key": key, "kmip_uid": "stale-uid"})
        call("kmip.sync_zfs_keys", job=True)
        row = encrypted_dataset_row(encrypted_dataset)
        assert row["encryption_key"] is None
        assert row["kmip_uid"] not in (None, "stale-uid", uid)

        # A UID the KMIP server does not know about cannot be resolved, so the key stays
        # unavailable instead of the sync blowing up.
        set_encrypted_dataset(encrypted_dataset, {"encryption_key": None, "kmip_uid": "unknown-uid"})
        call("kmip.update_memory_keys", {"zfs": {}})
        call("kmip.sync_zfs_keys", job=True)
        assert call("kmip.retrieve_zfs_keys") == {}

        set_encrypted_dataset(encrypted_dataset, {"encryption_key": key, "kmip_uid": None})
        call("kmip.update", {"manage_zfs_keys": False}, job=True)

    wait_for(lambda: call("kmip.kmip_sync_pending") is False)


def test_kmip_sed_keys_resynced_from_server(kmip_certificate):
    with global_sed_password() as password, sed_disk_password() as disk_id:
        with kmip_enabled(kmip_certificate["id"], manage_sed_disks=True):
            adv_uid = wait_for(lambda: advanced_row()["kmip_uid"])
            disk_uid = wait_for(lambda: disk_row(disk_id)["kmip_uid"])

            # A second sync finds both passwords on the KMIP server and only refreshes
            # the in-memory copies.
            call("kmip.update_memory_keys", {"sed": {"global_password": "", "sed_disks_keys": {}}})
            call("kmip.sync_sed_keys", job=True)
            assert call("kmip.sed_global_password") == password
            assert call("kmip.retrieve_sed_disks_keys")[disk_id] == password
            assert advanced_row()["kmip_uid"] == adv_uid
            assert disk_row(disk_id)["kmip_uid"] == disk_uid

            # Loading the keys on boot fetches them back from the KMIP server too.
            call("kmip.update_memory_keys", {"sed": {"global_password": "", "sed_disks_keys": {}}})
            call("kmip.initialize_keys", job=True)
            assert call("kmip.sed_global_password") == password
            assert call("kmip.retrieve_sed_disks_keys")[disk_id] == password

            # A password present in both the database and on the KMIP server has the
            # stale KMIP object destroyed and the password registered anew.
            call("datastore.update", "system.advanced", advanced_row()["id"], {"adv_sed_passwd": password})
            call("datastore.update", "storage.disk", disk_id, {"passwd": password}, {"prefix": "disk_"})
            call("kmip.sync_sed_keys", job=True)

            assert advanced_row()["sed_passwd"] == ""
            assert advanced_row()["kmip_uid"] not in (None, adv_uid)
            assert disk_row(disk_id)["passwd"] == ""
            assert disk_row(disk_id)["kmip_uid"] not in (None, disk_uid)

            call("kmip.update", {"manage_sed_disks": False}, job=True)
            wait_for(lambda: advanced_row()["sed_passwd"] == password)

    wait_for(lambda: call("kmip.kmip_sync_pending") is False)


def test_kmip_zfs_keys_not_synced_when_server_unreachable(kmip_certificate, encrypted_dataset):
    row = encrypted_dataset_row(encrypted_dataset)
    key = row["encryption_key"]

    # `validate=False` lets the (unreachable) configuration be saved so that the sync
    # path itself can be exercised against a dead server.
    call(
        "kmip.update",
        {
            "enabled": True,
            "server": KMIP_HOST,
            "port": DEAD_PORT,
            "certificate": kmip_certificate["id"],
            "certificate_authority": kmip_certificate["id"],
            "manage_zfs_keys": True,
            "validate": False,
        },
        job=True,
    )
    try:
        # The key never left the database and is therefore still pending sync.
        row = encrypted_dataset_row(encrypted_dataset)
        assert row["encryption_key"] == key
        assert row["kmip_uid"] is None
        assert call("kmip.kmip_sync_pending") is True

        # Disabling KMIP with keys pending sync is rejected...
        with pytest.raises(ValidationErrors) as ve:
            call("kmip.update", {"enabled": False, "validate": False}, job=True)

        assert any("kmip_update.enabled" == error.attribute for error in ve.value.errors), ve.value.errors
    finally:
        # ...unless `force_clear` is used to drop the pending keys.
        call("kmip.update", KMIP_RESET, job=True)

    # The dataset key was never on the KMIP server, so clearing must not have dropped it.
    assert encrypted_dataset_row(encrypted_dataset)["encryption_key"] == key
    wait_for(lambda: call("kmip.kmip_sync_pending") is False)


def test_kmip_sed_keys_pending_sync_cleared(kmip_certificate):
    with global_sed_password(), sed_disk_password():
        assert call("kmip.kmip_sync_pending") is False

        call(
            "kmip.update",
            {
                "enabled": True,
                "server": KMIP_HOST,
                "port": DEAD_PORT,
                "certificate": kmip_certificate["id"],
                "certificate_authority": kmip_certificate["id"],
                "manage_sed_disks": True,
                "validate": False,
            },
            job=True,
        )
        try:
            assert call("kmip.kmip_sync_pending") is True
        finally:
            call("kmip.update", KMIP_RESET, job=True)

        wait_for(lambda: call("kmip.kmip_sync_pending") is False)


def test_kmip_zfs_key_pulled_from_local_sources(encrypted_dataset):
    key = encrypted_dataset_row(encrypted_dataset)["encryption_key"]

    # KMIP is disabled, so these syncs pull keys back without ever reaching a server and
    # have to recover the key from a local source.

    # The database still holds the key.
    set_encrypted_dataset(encrypted_dataset, {"encryption_key": key, "kmip_uid": "unreachable-uid"})
    assert call("kmip.sync_zfs_keys", job=True) == []
    row = encrypted_dataset_row(encrypted_dataset)
    assert row["encryption_key"] == key
    assert row["kmip_uid"] is None

    # Only the in-memory cache holds the key.
    set_encrypted_dataset(encrypted_dataset, {"encryption_key": None, "kmip_uid": "unreachable-uid"})
    call("kmip.update_memory_keys", {"zfs": {encrypted_dataset: key}})
    assert call("kmip.sync_zfs_keys", job=True) == []

    row = encrypted_dataset_row(encrypted_dataset)
    assert row["encryption_key"] == key
    assert row["kmip_uid"] is None

    assert call("kmip.kmip_sync_pending") is False


def test_kmip_sed_keys_pulled_from_local_sources():
    adv_id = advanced_row()["id"]

    # KMIP is disabled, so this pull never reaches a server and has to recover both
    # passwords from a local source: the database for the disk, the cache for the global
    # password.
    with sed_disk_password() as disk_id:
        call("datastore.update", "storage.disk", disk_id, {"kmip_uid": "unreachable-uid"}, {"prefix": "disk_"})
        call("datastore.update", "system.advanced", adv_id, {"adv_sed_passwd": "", "adv_kmip_uid": "unreachable"})
        call("kmip.update_memory_keys", {"sed": {"global_password": SED_PASSWORD, "sed_disks_keys": {}}})
        try:
            assert call("kmip.sync_sed_keys", job=True) == []
            assert disk_row(disk_id)["passwd"] == SED_PASSWORD
            assert disk_row(disk_id)["kmip_uid"] is None
            assert advanced_row()["sed_passwd"] == SED_PASSWORD
            assert advanced_row()["kmip_uid"] is None
        finally:
            call("datastore.update", "system.advanced", adv_id, {"adv_sed_passwd": "", "adv_kmip_uid": None})
            call("kmip.update_memory_keys", {"sed": {"global_password": "", "sed_disks_keys": {}}})

    assert call("kmip.kmip_sync_pending") is False


def test_kmip_clear_sync_pending_removes_sed_uids():
    adv = advanced_row()
    with sed_disk_password() as disk_id:
        call("datastore.update", "storage.disk", disk_id, {"kmip_uid": "orphan-uid"}, {"prefix": "disk_"})
        call("datastore.update", "system.advanced", adv["id"], {"adv_kmip_uid": "orphan-uid"})
        try:
            call("kmip.clear_sync_pending_keys")
            assert disk_row(disk_id)["kmip_uid"] is None
            assert advanced_row()["kmip_uid"] is None
        finally:
            call("datastore.update", "system.advanced", adv["id"], {"adv_kmip_uid": None})


def test_kmip_reset_keys_with_unreachable_server():
    # Removing a key from a KMIP server that is not configured fails internally, but the
    # in-memory entry is dropped regardless so the caller never sees an error.
    call("kmip.update_memory_keys", {
        "zfs": {"tank/kmip-reset": "key"},
        "sed": {"global_password": "global", "sed_disks_keys": {"{uuid}kmip-reset": "disk"}},
    })
    try:
        call("kmip.reset_zfs_key", "tank/kmip-reset", "unreachable-uid")
        call("kmip.reset_sed_global_password", "unreachable-uid")
        call("kmip.reset_sed_disk_password", "{uuid}kmip-reset", "unreachable-uid")

        assert call("kmip.retrieve_zfs_keys") == {}
        assert call("kmip.retrieve_sed_disks_keys") == {}
        assert call("kmip.sed_global_password") == ""
    finally:
        call("kmip.update_memory_keys", {"zfs": {}, "sed": {"global_password": "", "sed_disks_keys": {}}})


def test_kmip_memory_keys_round_trip():
    original = call("kmip.kmip_memory_keys")
    assert set(original) == {"zfs", "sed"}
    assert set(original["sed"]) == {"global_password", "sed_disks_keys"}

    try:
        call("kmip.update_memory_keys", {
            "zfs": {"tank/kmip-memory-test": "key"},
            "sed": {"global_password": "global", "sed_disks_keys": {"{uuid}kmip-test": "disk"}},
        })
        assert call("kmip.retrieve_zfs_keys") == {"tank/kmip-memory-test": "key"}
        assert call("kmip.retrieve_sed_disks_keys") == {"{uuid}kmip-test": "disk"}
        assert call("kmip.sed_global_password") == "global"

        # Resetting individual entries drops them from the in-memory cache. A `null` KMIP
        # UID means there is nothing to remove from the KMIP server.
        call("kmip.reset_zfs_key", "tank/kmip-memory-test", None)
        call("kmip.reset_sed_disk_password", "{uuid}kmip-test", None)
        call("kmip.reset_sed_global_password", None)

        assert call("kmip.retrieve_zfs_keys") == {}
        assert call("kmip.retrieve_sed_disks_keys") == {}
        assert call("kmip.sed_global_password") == ""
    finally:
        call("kmip.update_memory_keys", original)


def test_kmip_sync_keys_noop_when_disabled():
    # Nothing is pending, so this is a no-op that must not raise.
    assert call("kmip.kmip_sync_pending") is False
    call("kmip.sync_keys")
    call("kmip.clear_sync_pending_keys")


def test_kmip_zfs_key_pull_failures(kmip_certificate, encrypted_dataset):
    key = encrypted_dataset_row(encrypted_dataset)["encryption_key"]

    # `manage_zfs_keys` is off, so this pulls keys back from the KMIP server. The server
    # is reachable but does not know the UID, so the dataset cannot be recovered.
    with kmip_enabled(kmip_certificate["id"]):
        set_encrypted_dataset(encrypted_dataset, {"encryption_key": None, "kmip_uid": "unknown-uid"})
        try:
            assert call("kmip.kmip_sync_pending") is True
            assert call("kmip.sync_zfs_keys", job=True) == [encrypted_dataset]
        finally:
            set_encrypted_dataset(encrypted_dataset, {"encryption_key": key, "kmip_uid": None})

    # With KMIP disabled there is no certificate to build a connection from either.
    set_encrypted_dataset(encrypted_dataset, {"encryption_key": None, "kmip_uid": "unreachable-uid"})
    try:
        assert call("kmip.sync_zfs_keys", job=True) == [encrypted_dataset]
    finally:
        set_encrypted_dataset(encrypted_dataset, {"encryption_key": key, "kmip_uid": None})
        call("alert.oneshot_delete", "KMIPZFSDatasetsSyncFailure")

    assert call("kmip.kmip_sync_pending") is False


def test_kmip_sed_keys_pull_failures(kmip_certificate):
    adv_id = advanced_row()["id"]

    def make_uids_stale(uid):
        call("datastore.update", "storage.disk", disk_id, {"passwd": "", "kmip_uid": uid}, {"prefix": "disk_"})
        call("datastore.update", "system.advanced", adv_id, {"adv_sed_passwd": "", "adv_kmip_uid": uid})

    def clear_uids():
        call("datastore.update", "storage.disk", disk_id, {"kmip_uid": None}, {"prefix": "disk_"})
        call("datastore.update", "system.advanced", adv_id, {"adv_sed_passwd": "", "adv_kmip_uid": None})
        call("kmip.update_memory_keys", {"sed": {"global_password": "", "sed_disks_keys": {}}})

    with sed_disk_password() as disk_id:
        # `manage_sed_disks` is off, so this pulls the passwords back from the KMIP
        # server. It is reachable but knows neither UID, so both passwords are lost.
        with kmip_enabled(kmip_certificate["id"]):
            make_uids_stale("unknown-uid")
            try:
                assert call("kmip.kmip_sync_pending") is True
                assert sorted(call("kmip.sync_sed_keys", job=True)) == sorted([disk_id, "Global SED Key"])
            finally:
                clear_uids()

        # With KMIP disabled there is no certificate to build a connection from either.
        # The global password is silently left alone in this case.
        make_uids_stale("unreachable-uid")
        try:
            assert call("kmip.sync_sed_keys", job=True) == [disk_id]
        finally:
            clear_uids()
            for klass in ("KMIPSEDDisksSyncFailure", "KMIPSEDGlobalPasswordSyncFailure"):
                call("alert.oneshot_delete", klass)

    assert call("kmip.kmip_sync_pending") is False


def test_kmip_change_server_fails_when_old_server_unreachable(kmip_certificate, encrypted_dataset):
    key = encrypted_dataset_row(encrypted_dataset)["encryption_key"]

    with kmip_enabled(kmip_certificate["id"], manage_zfs_keys=True):
        uid = wait_for(lambda: encrypted_dataset_row(encrypted_dataset)["kmip_uid"])

        # Point the configuration at a dead port without touching the stored UIDs, so the
        # migration cannot retrieve the keys from the "old" server.
        call("kmip.update", {"port": DEAD_PORT, "validate": False}, job=True)

        with pytest.raises(ClientException) as ce:
            call("kmip.update", {"change_server": True, "server": "localhost", "port": KMIP_PORT}, job=True)

        assert "Failed to sync keys" in str(ce.value), ce.value

        # The previous configuration was restored, so the key is still on the old server.
        config = call("kmip.config")
        assert config["server"] == KMIP_HOST
        assert config["manage_zfs_keys"] is True
        assert encrypted_dataset_row(encrypted_dataset)["kmip_uid"] == uid

        # Restore a working configuration so the key can be pulled back.
        call("kmip.update", {"port": KMIP_PORT}, job=True)
        call("kmip.update", {"manage_zfs_keys": False}, job=True)
        wait_for(lambda: encrypted_dataset_row(encrypted_dataset)["encryption_key"] == key)

    wait_for(lambda: call("kmip.kmip_sync_pending") is False)
