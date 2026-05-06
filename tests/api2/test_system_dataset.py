import errno
import os
import time
import uuid

from auto_config import ha
import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, pool, ssh
from middlewared.test.integration.utils.client import client

PASSPHRASE = 'passphrase'

# Subpath that lives under <pool>/.system/samba4 — a child dataset that
# travels with the parent in every migration scenario, so it's a stable
# sentinel location.
SENTINEL_REL_PATH = 'samba4/_sysds_test_sentinel'
SENTINEL_FULL_PATH = f'/var/db/system/{SENTINEL_REL_PATH}'


@pytest.fixture(scope="module")
def passphrase_encrypted_pool_session():
    with another_pool({"encryption": True, "encryption_options": {"passphrase": PASSPHRASE}}) as p:
        yield p["name"]


@pytest.fixture(scope="function")
def passphrase_encrypted_pool(passphrase_encrypted_pool_session):
    config = call("systemdataset.config")
    assert config["pool"] == pool

    for dataset in call("pool.dataset.query", [["name", "^", f"{passphrase_encrypted_pool_session}/"]]):
        try:
            call("pool.dataset.delete", dataset, {"recursive": True})
        except CallError as e:
            if e.errno != errno.ENOENT:
                raise

    # If root dataset is locked, let's unlock it here
    # It can be locked if some test locks it but does not unlock it later on and we should have
    # a clean slate whenever we are trying to test using this pool/root dataset
    if call("pool.dataset.get_instance", passphrase_encrypted_pool_session)["locked"]:
        call("pool.dataset.unlock", passphrase_encrypted_pool_session, {
            "datasets": [{"name": passphrase_encrypted_pool_session, "passphrase": PASSPHRASE}],
        })

    yield passphrase_encrypted_pool_session


@pytest.mark.parametrize("lock", [False, True])
def test_migrate_to_a_pool_with_passphrase_encrypted_root_dataset(passphrase_encrypted_pool, lock):
    if lock:
        call("pool.dataset.lock", passphrase_encrypted_pool, job=True)

    assert passphrase_encrypted_pool in call("systemdataset.pool_choices")

    call("systemdataset.update", {"pool": passphrase_encrypted_pool}, job=True)

    query_args = {
        "paths": [f"{passphrase_encrypted_pool}/.system"],
        "properties": ["encryption"]
    }
    ds = call("zfs.resource.query", query_args)[0]
    assert ds["properties"]["encryption"]["value"] == "off"

    call("systemdataset.update", {"pool": pool}, job=True)


def test_lock_passphrase_encrypted_pool_with_system_dataset(passphrase_encrypted_pool):
    call("systemdataset.update", {"pool": passphrase_encrypted_pool}, job=True)

    call("pool.dataset.lock", passphrase_encrypted_pool, job=True)

    query_args = {
        "paths": [f"{passphrase_encrypted_pool}/.system"],
        "properties": ["mounted"]
    }
    ds = call("zfs.resource.query", query_args)[0]
    assert ds["properties"]["mounted"]["raw"] == "yes"

    call("systemdataset.update", {"pool": pool}, job=True)


def test_system_dataset_mountpoints():
    system_config = call("systemdataset.config")
    for system_dataset_spec in call(
        "systemdataset.get_system_dataset_spec", system_config["pool"], system_config["uuid"]
    ):
        mount_point = system_dataset_spec.get("mountpoint") or os.path.join(
            system_config["path"], os.path.basename(system_dataset_spec["name"])
        )

        ds_stats = call("filesystem.stat", mount_point)
        assert ds_stats["uid"] == system_dataset_spec["chown_config"]["uid"]
        assert ds_stats["gid"] == system_dataset_spec["chown_config"]["gid"]
        assert ds_stats["mode"] & 0o777 == system_dataset_spec["chown_config"]["mode"]


def test_netdata_post_mount_action():
    # We rely on this to make sure system dataset post mount actions are working as intended
    ds_stats = call("filesystem.stat", "/var/db/system/netdata/ix_state")
    assert ds_stats["uid"] == 999, ds_stats
    assert ds_stats["gid"] == 997, ds_stats
    assert ds_stats["mode"] & 0o777 == 0o755, ds_stats


def _wait_for_standby_backup(ws_client, max_wait_time=300):
    """Wait for the remote (standby) controller to reconnect and report
    BACKUP after a sysdataset migration that triggered its reboot.

    Same pattern as tests/api2/test_006_pool_and_sysds.py::wait_for_standby.
    """
    time.sleep(5)
    sleep_time = 1

    waited = 0
    while waited < max_wait_time:
        if ws_client.call('failover.remote_connected'):
            break
        time.sleep(sleep_time)
        waited += sleep_time
    else:
        raise AssertionError(f'Standby did not reconnect after {max_wait_time}s')

    waited = 0
    while waited < max_wait_time:
        try:
            if ws_client.call('failover.call_remote', 'failover.status') == 'BACKUP':
                return
        except Exception:
            pass
        time.sleep(sleep_time)
        waited += sleep_time

    raise AssertionError(f'Standby did not reach BACKUP after {max_wait_time}s')


@pytest.mark.skipif(not ha, reason='HA-only test')
def test_ha_migration_preserves_partner_data():
    """When the user changes the system dataset pool on an HA cluster,
    data must round-trip cleanly through the migration plus the standby
    reboot. After standby comes back as BACKUP, its setup_impl runs
    against a state where mount/config may diverge — exercising the
    `_abandon_and_remount` path that preserves the partner's authoritative
    `<pool>/.system` data instead of replicating fallback writes onto it.

    This is the integration check for the recently-fixed data-loss bug
    in the fallback-recovery path.
    """
    sentinel_value = f'ha-roundtrip-{uuid.uuid4().hex}'

    with client() as ws_client:
        original_pool = ws_client.call('systemdataset.config')['pool']
        assert original_pool == pool, (
            f'unexpected starting pool {original_pool!r}, expected {pool!r}'
        )

        with another_pool() as extra:
            # Write sentinel on the current sysdataset.
            ssh(f'mkdir -p {os.path.dirname(SENTINEL_FULL_PATH)}')
            ssh(f'printf %s {sentinel_value!r} > {SENTINEL_FULL_PATH}')

            # Migrate to extra. This triggers the standby reboot.
            ws_client.call('systemdataset.update', {'pool': extra['name']}, job=True)
            _wait_for_standby_backup(ws_client)

            # Sentinel must round-trip via lzc.send/lzc.receive.
            assert ssh(f'cat {SENTINEL_FULL_PATH}').strip() == sentinel_value
            assert ws_client.call('systemdataset.config')['pool'] == extra['name']

            # Migrate back. Standby reboots again.
            ws_client.call('systemdataset.update', {'pool': original_pool}, job=True)
            _wait_for_standby_backup(ws_client)

            # Sentinel still intact on the original pool.
            assert ssh(f'cat {SENTINEL_FULL_PATH}').strip() == sentinel_value
            assert ws_client.call('systemdataset.config')['pool'] == original_pool

            # Cleanup the sentinel before another_pool teardown.
            ssh(f'rm -f {SENTINEL_FULL_PATH}')
