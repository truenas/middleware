import pytest

from middlewared.service_exception import CallError, InstanceNotFound, ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, mock

TASK_DATA = {
    "recursive": True,
    "lifetime_value": 1,
    "lifetime_unit": "DAY",
    "naming_schema": "auto-%Y-%m-%d_%H-%M",
}
BASE_REPLICATION = {
    "direction": "PUSH",
    "transport": "LOCAL",
    "recursive": False,
    "auto": False,
    "retention_policy": "NONE",
}


def test_create_extends_entry():
    """A freshly created task is extended with `vmware_sync`, `state` and a converted schedule."""
    with dataset("snapcrud_create") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            assert task["dataset"] == ds
            assert task["vmware_sync"] is False
            assert task["state"]["state"] == "PENDING"
            assert task["schedule"]["minute"] == "00"
            assert task["schedule"]["begin"] == "00:00"
            assert task["schedule"]["end"] == "23:59"

            # `state` and `vmware_sync` are read-only, they must not be written back to the database.
            row = call("datastore.query", "storage.task", [["id", "=", task["id"]]], {"get": True})
            assert row["task_dataset"] == ds


def test_query_reports_zettarepl_error_state():
    """When zettarepl itself is in an error state, every task reports that error as its state."""
    with dataset("snapcrud_state_error") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            with mock("zettarepl.get_state", return_value={"error": "Zettarepl is not running"}):
                assert call("pool.snapshottask.get_instance", task["id"])["state"] == "Zettarepl is not running"


def test_update():
    """Updating a task persists the new values and re-extends the returned entry."""
    with dataset("snapcrud_update") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            updated = call(
                "pool.snapshottask.update",
                task["id"],
                {
                    "lifetime_value": 5,
                    "lifetime_unit": "WEEK",
                    "schedule": {"minute": "30", "hour": "2"},
                },
            )

            assert updated["lifetime_value"] == 5
            assert updated["lifetime_unit"] == "WEEK"
            assert updated["schedule"]["minute"] == "30"
            assert updated["schedule"]["hour"] == "2"
            assert call("pool.snapshottask.get_instance", task["id"])["lifetime_value"] == 5


def test_update_disable_unbound_task():
    """A task that is not bound to any enabled replication task can be freely disabled.

    An enabled replication task bound to a *different* snapshot task must not get in the way.
    """
    with dataset("snapcrud_disable") as ds, dataset("snapcrud_disable_dst") as dst:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as bound:
            with replication_task(
                {
                    **BASE_REPLICATION,
                    "name": "snapcrud_disable",
                    "source_datasets": [ds],
                    "target_dataset": dst,
                    "periodic_snapshot_tasks": [bound["id"]],
                }
            ):
                with snapshot_task(
                    {
                        **TASK_DATA,
                        "dataset": ds,
                        "naming_schema": "unbound-%Y-%m-%d_%H-%M",
                    }
                ) as task:
                    assert call("pool.snapshottask.update", task["id"], {"enabled": False})["enabled"] is False


def test_update_disable_bound_to_enabled_replication_task():
    """A task bound to an enabled replication task can't be disabled."""
    with dataset("snapcrud_disable_bound") as ds, dataset("snapcrud_disable_bound_dst") as dst:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            with replication_task(
                {
                    **BASE_REPLICATION,
                    "name": "snapcrud_disable_bound",
                    "source_datasets": [ds],
                    "target_dataset": dst,
                    "periodic_snapshot_tasks": [task["id"]],
                }
            ):
                with pytest.raises(ValidationErrors) as ve:
                    call("pool.snapshottask.update", task["id"], {"enabled": False})

                assert "bound to enabled replication task" in ve.value.errors[0].errmsg


def test_create_validation_dataset_not_found():
    with pytest.raises(ValidationErrors) as ve:
        call("pool.snapshottask.create", {**TASK_DATA, "dataset": "invalid/nonexistent"})

    assert ve.value.errors[0].attribute == "periodic_snapshot_create.dataset"
    assert ve.value.errors[0].errmsg == "Dataset not found"


def test_create_validation_exclude_requires_recursive():
    with dataset("snapcrud_excl_nonrec") as ds:
        with pytest.raises(ValidationErrors) as ve:
            call(
                "pool.snapshottask.create",
                {
                    **TASK_DATA,
                    "dataset": ds,
                    "recursive": False,
                    "exclude": [f"{ds}/child"],
                },
            )

        assert ve.value.errors[0].attribute == "periodic_snapshot_create.exclude"
        assert "not necessary for non-recursive" in ve.value.errors[0].errmsg


def test_create_validation_exclude_must_be_a_descendant():
    with dataset("snapcrud_excl_foreign") as ds:
        with pytest.raises(ValidationErrors) as ve:
            call(
                "pool.snapshottask.create",
                {
                    **TASK_DATA,
                    "dataset": ds,
                    "recursive": True,
                    "exclude": ["some/other/dataset"],
                },
            )

        assert ve.value.errors[0].attribute == "periodic_snapshot_create.exclude.0"
        assert "should be a child or other descendant" in ve.value.errors[0].errmsg


def test_update_validation():
    """Validation also runs on update, against the merged (old + new) entry."""
    with dataset("snapcrud_update_validation") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds, "recursive": False}) as task:
            with pytest.raises(ValidationErrors) as ve:
                call("pool.snapshottask.update", task["id"], {"exclude": [f"{ds}/child"]})

            assert ve.value.errors[0].attribute == "periodic_snapshot_update.exclude"


def test_delete_last_task_bound_to_enabled_replication_task():
    """Deleting the only snapshot task an enabled replication task depends on is refused."""
    with dataset("snapcrud_delete_bound") as ds, dataset("snapcrud_delete_bound_dst") as dst:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            with replication_task(
                {
                    **BASE_REPLICATION,
                    "name": "snapcrud_delete_bound",
                    "source_datasets": [ds],
                    "target_dataset": dst,
                    "periodic_snapshot_tasks": [task["id"]],
                }
            ):
                with pytest.raises(CallError, match="last periodic snapshot task"):
                    call("pool.snapshottask.delete", task["id"])


def test_delete_task_bound_to_replication_task_with_multiple_tasks():
    """Deleting one of several snapshot tasks a replication task depends on is allowed."""
    with dataset("snapcrud_delete_multi") as ds, dataset("snapcrud_delete_multi_dst") as dst:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as first:
            with snapshot_task({**TASK_DATA, "dataset": ds, "naming_schema": "auto2-%Y-%m-%d_%H-%M"}) as second:
                with replication_task(
                    {
                        **BASE_REPLICATION,
                        "name": "snapcrud_delete_multi",
                        "source_datasets": [ds],
                        "target_dataset": dst,
                        "periodic_snapshot_tasks": [first["id"], second["id"]],
                    }
                ):
                    call("pool.snapshottask.delete", second["id"])

                    with pytest.raises(InstanceNotFound):
                        call("pool.snapshottask.get_instance", second["id"])


def test_delete_task_not_bound_to_an_existing_replication_task():
    """An unbound task is deletable even while other enabled replication tasks exist."""
    with dataset("snapcrud_delete_unbound") as ds, dataset("snapcrud_delete_unbound_dst") as dst:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as bound:
            with replication_task(
                {
                    **BASE_REPLICATION,
                    "name": "snapcrud_delete_unbound",
                    "source_datasets": [ds],
                    "target_dataset": dst,
                    "periodic_snapshot_tasks": [bound["id"]],
                }
            ):
                unbound = call(
                    "pool.snapshottask.create",
                    {
                        **TASK_DATA,
                        "dataset": ds,
                        "naming_schema": "unbound-%Y-%m-%d_%H-%M",
                    },
                )
                call("pool.snapshottask.delete", unbound["id"])

                with pytest.raises(InstanceNotFound):
                    call("pool.snapshottask.get_instance", unbound["id"])


def test_delete_with_fixate_removal_date_and_no_snapshots():
    """`fixate_removal_date` is a no-op when the task owns no snapshots."""
    with dataset("snapcrud_delete_fixate_empty") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds}) as task:
            assert call("pool.snapshottask.delete_will_change_retention_for", task["id"]) == {}

            call("pool.snapshottask.delete", task["id"], {"fixate_removal_date": True})

            with pytest.raises(InstanceNotFound):
                call("pool.snapshottask.get_instance", task["id"])


def test_snapshot_task_is_not_deleted_when_deleting_a_child_dataset():
    with dataset("parent") as parent:
        with dataset("parent/child") as child:
            with snapshot_task(
                {
                    "dataset": parent,
                    "recursive": True,
                    "lifetime_value": 1,
                    "lifetime_unit": "DAY",
                    "naming_schema": "%Y%m%d%H%M",
                }
            ) as t:
                call("pool.dataset.delete", child)

                assert call("pool.snapshottask.get_instance", t["id"])
