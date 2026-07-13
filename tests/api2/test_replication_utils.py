import pytest

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


def test_target_unmatched_snapshots():
    with dataset("src") as src:
        with dataset("dst") as dst:
            # Target has a snapshot that does not exist on the source.
            call("pool.snapshot.create", {"dataset": dst, "name": "snap-2022-01-01-00-00"})

            result = call("replication.target_unmatched_snapshots", "PUSH", [src], dst, "LOCAL", None)

            assert result == {dst: ["snap-2022-01-01-00-00"]}


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
