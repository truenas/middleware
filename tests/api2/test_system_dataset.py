import errno
import os
import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, pool


PASSPHRASE = 'passphrase'


@pytest.fixture(scope="module")
def passphrase_encrypted_pool_session():
    with another_pool({"encryption": True, "encryption_options": {"passphrase": PASSPHRASE}}) as p:
        yield p["name"]


@pytest.fixture(scope="function")
def passphrase_encrypted_pool(passphrase_encrypted_pool_session):
    config = call("systemdataset.config")
    assert config["pool"] == pool

    try:
        call("pool.dataset.delete", passphrase_encrypted_pool_session, {"recursive": True})
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
    ds = call("zfs.resource.query_impl", query_args)[0]
    assert ds["properties"]["encryption"]["value"] == "off"

    call("systemdataset.update", {"pool": pool}, job=True)


def test_lock_passphrase_encrypted_pool_with_system_dataset(passphrase_encrypted_pool):
    call("systemdataset.update", {"pool": passphrase_encrypted_pool}, job=True)

    call("pool.dataset.lock", passphrase_encrypted_pool, job=True)

    query_args = {
        "paths": [f"{passphrase_encrypted_pool}/.system"],
        "properties": ["mounted"]
    }
    ds = call("zfs.resource.query_impl", query_args)[0]
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
