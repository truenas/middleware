import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import task


@pytest.mark.parametrize("has_pull", [False, True])
def test_create_pull_replication(has_pull):
    with dataset("src") as src:
        with dataset("dst") as dst:
            payload = {
                "name": "Test",
                "direction": "PULL",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": dst,
                "recursive": True,
                "naming_schema": ["%Y-%m-%d-%H-%M-%S"],
                "retention_policy": "NONE",
                "auto": False,
            }

            if has_pull:
                role = "REPLICATION_TASK_WRITE_PULL"
            else:
                role = "REPLICATION_TASK_WRITE"
            with unprivileged_user_client([role]) as c:
                if has_pull:
                    task = c.call("replication.create", payload)
                    c.call("replication.delete", task["id"])
                else:
                    with pytest.raises(ValidationErrors) as ve:
                        c.call("replication.create", payload)

                    assert ve.value.errors[0].attribute == "replication_create.direction"


@pytest.mark.parametrize("has_pull", [False, True])
def test_update_pull_replication(has_pull):
    with dataset("src") as src:
        with dataset("dst") as dst:
            with task({
                "name": "Test",
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": dst,
                "recursive": True,
                "also_include_naming_schema": ["%Y-%m-%d-%H-%M-%S"],
                "retention_policy": "NONE",
                "auto": False,
            }) as t:
                payload = {
                    "direction": "PULL",
                    "naming_schema": ["%Y-%m-%d-%H-%M-%S"],
                    "also_include_naming_schema": [],
                }

                if has_pull:
                    role = "REPLICATION_TASK_WRITE_PULL"
                else:
                    role = "REPLICATION_TASK_WRITE"
                with unprivileged_user_client([role]) as c:
                    if has_pull:
                        c.call("replication.update", t["id"], payload)
                    else:
                        with pytest.raises(ValidationErrors) as ve:
                            c.call("replication.update", t["id"], payload)

                        assert ve.value.errors[0].attribute == "replication_update.direction"


@pytest.mark.parametrize("has_pull", [False, True])
def test_restore_push_replication(has_pull):
    with dataset("src") as src:
        with dataset("dst") as dst:
            with task({
                "name": "Test",
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": dst,
                "recursive": True,
                "also_include_naming_schema": ["%Y-%m-%d-%H-%M-%S"],
                "retention_policy": "NONE",
                "auto": False,
            }) as t:
                with dataset("dst2") as dst2:
                    payload = {
                        "name": "Test restore",
                        "target_dataset": dst2,
                    }

                    if has_pull:
                        role = "REPLICATION_TASK_WRITE_PULL"
                    else:
                        role = "REPLICATION_TASK_WRITE"
                    with unprivileged_user_client([role]) as c:
                        if has_pull:
                            rt = c.call("replication.restore", t["id"], payload)
                            c.call("replication.delete", rt["id"])
                        else:
                            with pytest.raises(ValidationErrors) as ve:
                                c.call("replication.restore", t["id"], payload)

                            assert ve.value.errors[0].attribute == "replication_create.direction"
