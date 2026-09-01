import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, mock

from truenas_api_client import ClientException


MOCK_GET_STATE_GLOBAL_ERROR = """\
    async def mock(self):
        return {"error": "Simulated global zettarepl failure"}
"""
MOCK_GET_STATE_TASK_STATE = """\
    async def mock(self):
        class Tasks(dict):
            def get(self, key, default=None):
                return %r
        return {"tasks": Tasks()}
"""


def test_run_onetime_global_error_state():
    with dataset("onetime_src") as src, dataset("onetime_dst") as dst:
        with mock("zettarepl.get_state", MOCK_GET_STATE_GLOBAL_ERROR):
            with pytest.raises(ClientException, match="Simulated global zettarepl failure"):
                call(
                    "replication.run_onetime",
                    {
                        "direction": "PUSH",
                        "transport": "LOCAL",
                        "source_datasets": [src],
                        "target_dataset": dst,
                        "recursive": False,
                        "name_regex": ".+",
                        "retention_policy": "NONE",
                    },
                    job=True,
                )


@pytest.mark.parametrize(
    "task_state,match",
    [
        ({"state": "ERROR", "error": "Simulated task error"}, "Simulated task error"),
        ({"state": "HOLD", "reason": "Simulated task hold"}, "Simulated task hold"),
        ({"state": "RUNNING"}, None),
    ],
)
def test_run_onetime_task_state_error(task_state, match):
    with dataset("onetime_src") as src, dataset("onetime_dst") as dst:
        with mock("zettarepl.get_state", MOCK_GET_STATE_TASK_STATE % task_state):
            with pytest.raises(Exception) as e:
                call(
                    "replication.run_onetime",
                    {
                        "direction": "PUSH",
                        "transport": "LOCAL",
                        "source_datasets": [src],
                        "target_dataset": dst,
                        "recursive": False,
                        "name_regex": ".+",
                        "retention_policy": "NONE",
                    },
                    job=True,
                )

            if match:
                assert match in str(e.value)


def test_zettarepl_load_state():
    """`zettarepl.load_state` restores persisted task states from the database."""
    with dataset("loadstate_src") as src, dataset("loadstate_dst") as dst:
        with snapshot_task(
            {
                "dataset": src,
                "recursive": False,
                "lifetime_value": 1,
                "lifetime_unit": "DAY",
                "naming_schema": "auto-%Y-%m-%d_%H-%M",
                "schedule": {"minute": "0", "hour": "0", "dom": "1", "month": "1", "dow": "1"},
                "enabled": True,
            }
        ) as st:
            call("pool.snapshottask.run", st["id"], job=True)

            with replication_task(
                {
                    "name": "test_zettarepl_load_state",
                    "direction": "PUSH",
                    "transport": "LOCAL",
                    "source_datasets": [src],
                    "target_dataset": dst,
                    "recursive": False,
                    "also_include_naming_schema": ["auto-%Y-%m-%d_%H-%M"],
                    "auto": False,
                    "retention_policy": "NONE",
                }
            ) as rt:
                call("replication.run", rt["id"], job=True)

                with (
                    snapshot_task(
                        {
                            "dataset": src,
                            "recursive": False,
                            "lifetime_value": 1,
                            "lifetime_unit": "DAY",
                            "naming_schema": "never-%Y-%m-%d_%H-%M",
                            "schedule": {"minute": "0", "hour": "0", "dom": "1", "month": "1", "dow": "1"},
                            "enabled": True,
                        }
                    ) as never_run_st,
                    replication_task(
                        {
                            "name": "test_zettarepl_load_state never run",
                            "direction": "PUSH",
                            "transport": "LOCAL",
                            "source_datasets": [src],
                            "target_dataset": "data/dst",
                            "recursive": False,
                            "name_regex": ".+",
                            "auto": False,
                            "retention_policy": "NONE",
                        }
                    ) as never_run_rt,
                ):
                    call("zettarepl.load_state")

                    # A task that has never run has an empty persisted state, and loading it must not register a
                    # state entry for the task
                    assert call("pool.snapshottask.get_instance", never_run_st["id"])["state"]["state"] == "PENDING"
                    assert call("replication.get_instance", never_run_rt["id"])["state"]["state"] == "PENDING"

                assert call("pool.snapshottask.get_instance", st["id"])["state"]["state"] == "FINISHED"
                assert call("replication.get_instance", rt["id"])["state"]["state"] == "FINISHED"


def test_zettarepl_terminate_and_restart():
    """`zettarepl.terminate` flushes the task states and stops the zettarepl process."""
    call("zettarepl.terminate")
    assert call("zettarepl.is_running") is False

    call("zettarepl.start")
    assert call("zettarepl.is_running") is True
