import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.keychain import localhost_ssh_credentials, ssh_keypair
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, mock, poll, pool


@pytest.fixture(scope="module")
def ssh_credentials():
    with localhost_ssh_credentials(username="root") as c:
        yield c


def test_zettarepl_definition_options():
    """Task options are translated into the zettarepl task definition."""
    with replication_task(
        {
            "name": "test_definition_options",
            "direction": "PUSH",
            "transport": "LOCAL",
            # Replicating the pool root implicitly excludes the system dataset.
            "source_datasets": [pool],
            "target_dataset": "data/dst",
            "recursive": True,
            "also_include_naming_schema": ["auto-%Y-%m-%d-%H-%M"],
            "auto": False,
            "retention_policy": "CUSTOM",
            "lifetime_value": 2,
            "lifetime_unit": "WEEK",
            "lifetimes": [
                {"schedule": {"hour": "0"}, "lifetime_value": 1, "lifetime_unit": "HOUR"},
                {"schedule": {"hour": "0", "dow": "1"}, "lifetime_value": 1, "lifetime_unit": "MONTH"},
            ],
            "restrict_schedule": {"minute": "*/2"},
            "properties_exclude": ["sharenfs"],
            "properties_override": {"sharesmb": "off"},
            "encryption": True,
            "encryption_inherit": True,
        }
    ) as task:
        definition, hold_tasks = call("zettarepl.get_definition")
        d = definition["replication-tasks"][f"task_{task['id']}"]

        assert f"{pool}/.system" in d["exclude"]
        assert d["encryption"] == "inherit"
        assert d["restrict-schedule"]["minute"] == "*/2"
        assert d["lifetime"] == "PT1209600S"
        assert d["lifetimes"]["lifetime_0"]["lifetime"] == "PT3600S"
        assert d["lifetimes"]["lifetime_1"]["lifetime"] == "PT2592000S"
        assert "sharenfs" in d["properties-exclude"]
        assert "mountpoint" in d["properties-exclude"]
        assert d["properties-override"] == {"sharesmb": "off"}


def test_zettarepl_definition_ssh_netcat(ssh_credentials):
    """SSH+NETCAT specific options are translated into the zettarepl transport definition."""
    with dataset("netcat_src") as src:
        with replication_task(
            {
                "name": "test_definition_ssh_netcat",
                "direction": "PUSH",
                "transport": "SSH+NETCAT",
                "ssh_credentials": ssh_credentials["credentials"]["id"],
                "netcat_active_side": "LOCAL",
                "netcat_active_side_listen_address": "127.0.0.1",
                "netcat_active_side_port_min": 1024,
                "netcat_active_side_port_max": 50000,
                "netcat_passive_side_connect_address": "127.0.0.1",
                "source_datasets": [src],
                "target_dataset": "data/dst",
                "recursive": False,
                "also_include_naming_schema": ["auto-%Y-%m-%d-%H-%M"],
                "auto": False,
                "retention_policy": "NONE",
                "encryption": True,
                "encryption_inherit": False,
                "encryption_key": "0" * 64,
                "encryption_key_format": "HEX",
                "encryption_key_location": "/tmp/test_definition_ssh_netcat.key",
            }
        ) as task:
            definition, hold_tasks = call("zettarepl.get_definition")
            d = definition["replication-tasks"][f"task_{task['id']}"]

            assert d["transport"]["type"] == "ssh+netcat"
            assert d["transport"]["active-side"] == "local"
            assert d["transport"]["active-side-listen-address"] == "127.0.0.1"
            assert d["transport"]["active-side-min-port"] == 1024
            assert d["transport"]["active-side-max-port"] == 50000
            assert d["transport"]["passive-side-connect-address"] == "127.0.0.1"
            assert d["encryption"] == {
                "key": "0" * 64,
                "key-format": "hex",
                "key-location": "/tmp/test_definition_ssh_netcat.key",
            }


def test_zettarepl_definition_ssh_netcat_defaults(ssh_credentials):
    """Optional SSH+NETCAT parameters are simply absent from the transport definition."""
    with dataset("netcat_min_src") as src:
        with replication_task(
            {
                "name": "test_definition_ssh_netcat_defaults",
                "direction": "PUSH",
                "transport": "SSH+NETCAT",
                "ssh_credentials": ssh_credentials["credentials"]["id"],
                "netcat_active_side": "REMOTE",
                "source_datasets": [src],
                "target_dataset": "data/dst",
                "recursive": False,
                "also_include_naming_schema": ["auto-%Y-%m-%d-%H-%M"],
                "auto": False,
                "retention_policy": "NONE",
            }
        ) as task:
            definition, hold_tasks = call("zettarepl.get_definition")
            d = definition["replication-tasks"][f"task_{task['id']}"]

            assert d["transport"]["type"] == "ssh+netcat"
            assert d["transport"]["active-side"] == "remote"
            for key in (
                "active-side-listen-address",
                "active-side-min-port",
                "active-side-max-port",
                "passive-side-connect-address",
            ):
                assert key not in d["transport"]


RAISE_GET_DEFINITION_ERROR = """\
    async def mock(self):
        raise Exception("Simulated definition generation failure")
"""


def test_zettarepl_definition_generation_error():
    """A `get_definition` failure puts zettarepl into a global error state and is recoverable."""
    with dataset("gen_error_src") as src:
        with replication_task(
            {
                "name": "test_definition_generation_error",
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": "data/dst",
                "recursive": False,
                "name_regex": ".+",
                "auto": False,
                "retention_policy": "NONE",
            }
        ) as task:
            try:
                with mock("zettarepl.get_definition", RAISE_GET_DEFINITION_ERROR):
                    with pytest.raises(CallError, match="Internal error"):
                        call("zettarepl.start")

                    # `update_tasks` does not raise, it just records the error.
                    call("zettarepl.update_tasks")

                    state = call("zettarepl.get_state")
                    assert state["error"]["state"] == "ERROR"
                    assert "Simulated definition generation failure" in state["error"]["error"]

                    # Every task reports the global error as its state.
                    assert call("replication.get_instance", task["id"])["state"]["state"] == "ERROR"
            finally:
                call("zettarepl.update_tasks")

            assert "tasks" in call("zettarepl.get_state")


def test_replication_task_hold_when_network_activity_denied(ssh_credentials):
    """Non-local replication tasks are held while replication network activity is denied."""
    with dataset("activity_src") as src:
        with replication_task(
            {
                "name": "test_network_activity_hold",
                "direction": "PUSH",
                "transport": "SSH",
                "ssh_credentials": ssh_credentials["credentials"]["id"],
                "source_datasets": [src],
                "target_dataset": "data/dst",
                "recursive": False,
                "name_regex": ".+",
                "auto": False,
                "retention_policy": "NONE",
            }
        ) as task:
            original = call("network.configuration.config")["activity"]
            try:
                call("network.configuration.update", {"activity": {"type": "DENY", "activities": ["replication"]}})
                call("zettarepl.update_tasks")

                state = call("replication.get_instance", task["id"])["state"]
                assert state["state"] == "HOLD"
                assert "Replication network activity is disabled" in state["reason"]
            finally:
                call("network.configuration.update", {"activity": original})
                call("zettarepl.update_tasks")


def test_replication_task_hold_when_pool_offline():
    """Tasks on an offline pool are held."""
    with dataset("offline_src") as src:
        with replication_task(
            {
                "name": "test_pool_offline_hold",
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": "data/dst",
                "recursive": False,
                "name_regex": ".+",
                "auto": False,
                "retention_policy": "NONE",
            }
        ) as task:
            try:
                with mock("pool.query", return_value=[{"name": pool, "status": "OFFLINE"}]):
                    call("zettarepl.update_tasks")

                    state = call("replication.get_instance", task["id"])["state"]
                    assert state["state"] == "HOLD"
                    assert f"Pool {pool} is offline" in state["reason"]
            finally:
                call("zettarepl.update_tasks")


def test_replication_task_hold_when_ssh_key_pair_missing():
    """A task whose SSH connection references a deleted key pair is held with an explanation."""
    with ssh_keypair() as keypair:
        connection = call(
            "keychaincredential.setup_ssh_connection",
            {
                "private_key": {"generate_key": False, "existing_key_id": keypair["id"]},
                "connection_name": "test_zettarepl_missing_keypair",
                "setup_type": "MANUAL",
                "manual_setup": {
                    "host": "localhost",
                    "username": "root",
                    "remote_host_key": "ssh-rsa DUMMY",
                },
            },
        )
        try:
            with dataset("keypair_src") as src:
                with replication_task(
                    {
                        "name": "test_missing_keypair_hold",
                        "direction": "PUSH",
                        "transport": "SSH",
                        "ssh_credentials": connection["id"],
                        "source_datasets": [src],
                        "target_dataset": "data/dst",
                        "recursive": False,
                        "name_regex": ".+",
                        "auto": False,
                        "retention_policy": "NONE",
                    }
                ) as task:
                    call("datastore.delete", "system.keychaincredential", keypair["id"])
                    call("zettarepl.update_tasks")

                    state = call("replication.get_instance", task["id"])["state"]
                    assert state["state"] == "HOLD"
                    assert "Error while querying SSH key pair" in state["reason"]
        finally:
            call("keychaincredential.delete", connection["id"])


def test_replication_task_definition_error_when_snapshot_task_pool_missing():
    """A replication task bound to a held periodic snapshot task reports a definition error."""
    with dataset("deferr_src") as src, dataset("deferr_dst") as dst:
        with snapshot_task(
            {
                "dataset": src,
                "recursive": False,
                "lifetime_value": 1,
                "lifetime_unit": "WEEK",
                "naming_schema": "auto-%Y%m%d.%H%M%S-1w",
                "schedule": {},
            }
        ) as st:
            with replication_task(
                {
                    "name": "test_snapshot_task_definition_error",
                    "direction": "PUSH",
                    "transport": "LOCAL",
                    "source_datasets": [src],
                    "target_dataset": dst,
                    "recursive": False,
                    "periodic_snapshot_tasks": [st["id"]],
                    "auto": True,
                    "retention_policy": "NONE",
                }
            ) as rt:
                try:
                    call("datastore.update", "storage.task", st["id"], {"task_dataset": "nonexistent_pool_zrepl/foo"})
                    call("zettarepl.update_tasks")

                    # The snapshot task itself is held because its pool does not exist.
                    assert call("pool.snapshottask.get_instance", st["id"])["state"]["state"] == "HOLD"

                    # The replication task references a periodic snapshot task that is no longer in
                    # the definition, which is reported (asynchronously, by the zettarepl process) as
                    # a definition error.
                    poll(
                        lambda: call("replication.get_instance", rt["id"])["state"],
                        condition=lambda state: (
                            state["state"] == "ERROR" and "Periodic snapshot task" in state["error"]
                        ),
                        timeout=60,
                        message="The replication task never reported a definition error",
                    )
                finally:
                    call("datastore.update", "storage.task", st["id"], {"task_dataset": src})
                    call("zettarepl.update_tasks")
