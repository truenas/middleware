import errno

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.keychain import ssh_keypair
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, pool, ssh


@pytest.fixture(scope="module")
def localhost_ssh_connection():
    credential = call("keychaincredential.create", {
        "name": "key",
        "type": "SSH_KEY_PAIR",
        "attributes": call("keychaincredential.generate_ssh_key_pair"),
    })
    try:
        token = call("auth.generate_token", 600, {}, False)
        connection = call("keychaincredential.remote_ssh_semiautomatic_setup", {
            "name": "localhost",
            "url": "http://localhost",
            "token": token,
            "private_key": credential["id"],
        })
        try:
            yield connection["id"]
        finally:
            call("keychaincredential.delete", connection["id"])
    finally:
        call("keychaincredential.delete", credential["id"])


@pytest.mark.parametrize("transport", ["SSH", "SSH+NETCAT"])
def test_list_datasets_ssh(localhost_ssh_connection, transport):
    assert pool in call("replication.list_datasets", transport, localhost_ssh_connection)


def test_replication_pair():
    public_key = call("keychaincredential.generate_ssh_key_pair")["public_key"]

    result = call("replication.pair", {
        "hostname": "127.0.0.1",
        "public-key": public_key,
        "user": "root",
    })

    assert result["ssh_port"] == call("ssh.config")["tcpport"]
    assert "127.0.0.1 ssh-" in result["ssh_hostkey"]


def test_new_snapshot_name():
    assert call("replication.new_snapshot_name", "auto-%Y").startswith("auto-20")


def test_list_naming_schemas():
    with dataset("src") as src:
        with snapshot_task({
            "dataset": src,
            "recursive": False,
            "lifetime_value": 1,
            "lifetime_unit": "WEEK",
            "naming_schema": "auto-%Y%m%d.%H%M%S-1w",
            "schedule": {},
        }):
            with replication_task({
                "name": "test_list_naming_schemas",
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": "data",
                "recursive": False,
                "also_include_naming_schema": ["snap-%Y%m%d-%H%M-1m"],
                "auto": False,
                "retention_policy": "NONE",
            }):
                naming_schemas = call("replication.list_naming_schemas")

                assert "auto-%Y%m%d.%H%M%S-1w" in naming_schemas
                assert "snap-%Y%m%d-%H%M-1m" in naming_schemas


def test_count_eligible_manual_snapshots():
    with dataset("src") as src:
        call("pool.snapshot.create", {"dataset": src, "name": "snap-2022-01-01-00-00"})

        result = call("replication.count_eligible_manual_snapshots", {
            "datasets": [src],
            "naming_schema": ["snap-%Y-%m-%d-%H-%M"],
            "transport": "LOCAL",
        })

        assert result["total"] == 1
        assert result["eligible"] == 1


def test_count_eligible_manual_snapshots_name_regex():
    with dataset("src") as src:
        call("pool.snapshot.create", {"dataset": src, "name": "manual-1"})
        call("pool.snapshot.create", {"dataset": src, "name": "other-1"})

        result = call("replication.count_eligible_manual_snapshots", {
            "datasets": [src],
            "name_regex": "manual-.+",
            "transport": "LOCAL",
        })

        assert result["total"] == 2
        assert result["eligible"] == 1


def test_count_eligible_manual_snapshots_invalid_name_regex():
    with dataset("src") as src:
        call("pool.snapshot.create", {"dataset": src, "name": "manual-1"})

        with pytest.raises(CallError, match="Invalid `name_regex`"):
            call("replication.count_eligible_manual_snapshots", {
                "datasets": [src],
                "name_regex": "(",
                "transport": "LOCAL",
            })


def test_count_eligible_manual_snapshots_naming_schema_and_name_regex():
    with pytest.raises(CallError, match="cannot be used simultaneously"):
        call("replication.count_eligible_manual_snapshots", {
            "datasets": [f"{pool}/whatever"],
            "naming_schema": ["snap-%Y-%m-%d-%H-%M"],
            "name_regex": "manual-.+",
            "transport": "LOCAL",
        })


def test_count_eligible_manual_snapshots_no_naming_schema_or_name_regex():
    with dataset("src") as src:
        with pytest.raises(CallError, match="must be specified"):
            call("replication.count_eligible_manual_snapshots", {
                "datasets": [src],
                "transport": "LOCAL",
            })


@pytest.mark.parametrize("direction", ["PUSH", "PULL"])
def test_target_unmatched_snapshots(direction):
    with dataset("src") as src:
        with dataset("dst") as dst:
            # Target has a snapshot that does not exist on the source.
            call("pool.snapshot.create", {"dataset": dst, "name": "snap-2022-01-01-00-00"})

            result = call("replication.target_unmatched_snapshots", direction, [src], dst, "LOCAL", None)

            assert result == {dst: ["snap-2022-01-01-00-00"]}


def test_target_unmatched_snapshots_all_matched():
    with dataset("src") as src:
        with dataset("dst") as dst:
            # Both sides have the same snapshot, so nothing is unmatched.
            call("pool.snapshot.create", {"dataset": src, "name": "snap-2022-01-01-00-00"})
            call("pool.snapshot.create", {"dataset": dst, "name": "snap-2022-01-01-00-00"})

            assert call("replication.target_unmatched_snapshots", "PUSH", [src], dst, "LOCAL", None) == {}


def test_target_unmatched_snapshots_listing_error():
    """A shell error (nonexistent source dataset) is converted into a `CallError`."""
    with dataset("dst") as dst:
        call("pool.snapshot.create", {"dataset": dst, "name": "snap-2022-01-01-00-00"})

        with pytest.raises(CallError, match="does not exist"):
            call("replication.target_unmatched_snapshots", "PUSH", [f"{pool}/nonexistent_zettarepl_src"], dst,
                 "LOCAL", None)


def test_create_dataset():
    name = f"{pool}/test_replication_create_dataset"
    try:
        call("replication.create_dataset", name, "LOCAL", None)

        assert name in ssh("zfs list -H -o name").splitlines()
    finally:
        ssh(f"zfs destroy -r {name}", check=False)


def test_replication_config_update():
    original = call("replication.config.config")["max_parallel_replication_tasks"]
    try:
        updated = call("replication.config.update", {"max_parallel_replication_tasks": 3})
        assert updated["max_parallel_replication_tasks"] == 3
        assert call("replication.config.config")["max_parallel_replication_tasks"] == 3
    finally:
        call("replication.config.update", {"max_parallel_replication_tasks": original})


def test_list_datasets_ssh_without_credentials():
    with pytest.raises(CallError, match="You should pass SSH credentials"):
        call("replication.list_datasets", "SSH")


def test_list_datasets_ssh_bad_host_key():
    """A host key mismatch produces the man-in-the-middle warning."""
    wrong_host_key = call("keychaincredential.generate_ssh_key_pair")["public_key"]
    with ssh_keypair() as keypair:
        connection = call("keychaincredential.setup_ssh_connection", {
            "private_key": {"generate_key": False, "existing_key_id": keypair["id"]},
            "connection_name": "test_zettarepl_bad_host_key",
            "setup_type": "MANUAL",
            "manual_setup": {
                "host": "localhost",
                "username": "root",
                "remote_host_key": wrong_host_key,
            },
        })
        try:
            with pytest.raises(CallError, match="Remote host identification has changed") as e:
                call("replication.list_datasets", "SSH", connection["id"])

            assert e.value.errno == errno.EACCES
        finally:
            call("keychaincredential.delete", connection["id"])


def test_list_datasets_ssh_unreachable():
    """A connection failure is converted into a `CallError` with `EACCES`."""
    host_key = call("keychaincredential.remote_ssh_host_key_scan", {"host": "localhost"})
    with ssh_keypair() as keypair:
        connection = call("keychaincredential.setup_ssh_connection", {
            "private_key": {"generate_key": False, "existing_key_id": keypair["id"]},
            "connection_name": "test_zettarepl_unreachable",
            "setup_type": "MANUAL",
            "manual_setup": {
                "host": "localhost",
                "port": 1,
                "username": "root",
                "remote_host_key": host_key,
                "connect_timeout": 5,
            },
        })
        try:
            with pytest.raises(CallError) as e:
                call("replication.list_datasets", "SSH", connection["id"])

            assert e.value.errno == errno.EACCES
        finally:
            call("keychaincredential.delete", connection["id"])


def test_create_recursive_snapshot_with_exclude():
    with dataset("snapexcl") as parent:
        with dataset("snapexcl/keep") as keep:
            with dataset("snapexcl/skip") as skip:
                call("zettarepl.create_recursive_snapshot_with_exclude", parent, "excl-snap-1", [skip])

                snapshots = ssh("zfs list -t snapshot -H -o name").splitlines()
                assert f"{parent}@excl-snap-1" in snapshots
                assert f"{keep}@excl-snap-1" in snapshots
                assert f"{skip}@excl-snap-1" not in snapshots
