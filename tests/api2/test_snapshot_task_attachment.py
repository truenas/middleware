import pytest

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call

TASK_DATA = {
    "recursive": True,
    "lifetime_value": 1,
    "lifetime_unit": "DAY",
    "naming_schema": "%Y%m%d%H%M",
}


def snapshot_task_attachments(ds):
    return [a for a in call("pool.dataset.attachments", ds) if a["type"] == "Snapshot Task"]


def test_attachment_delegate_query():
    """The delegate reports tasks whose dataset lives under the queried path, and nothing else."""
    with dataset("snapattach_src") as ds, dataset("snapattach_other") as other:
        with snapshot_task({**TASK_DATA, "dataset": ds}):
            assert snapshot_task_attachments(ds) == [
                {
                    "type": "Snapshot Task",
                    "service": None,
                    "attachments": [ds],
                }
            ]

            # A task on a different dataset is not an attachment of that path.
            assert snapshot_task_attachments(other) == []


def test_attachment_delegate_query_ignores_disabled_tasks():
    with dataset("snapattach_disabled") as ds:
        with snapshot_task({**TASK_DATA, "dataset": ds, "enabled": False}):
            assert snapshot_task_attachments(ds) == []


def test_attachment_delegate_delete():
    """Deleting the parent dataset deletes the task through the delegate's `delete`."""
    with dataset("parent") as parent:
        with dataset("parent/child") as child:
            with snapshot_task({**TASK_DATA, "dataset": child}) as task:
                call("pool.dataset.delete", parent, {"recursive": True})

                with pytest.raises(InstanceNotFound):
                    call("pool.snapshottask.get_instance", task["id"])


def test_attachment_delegate_toggle():
    """Exporting/importing a pool disables/re-enables its snapshot tasks via the delegate."""
    pool_name = "test_snapshottask_toggle"
    with another_pool({"name": pool_name}) as new_pool:
        src = f"{pool_name}/src"
        call("pool.dataset.create", {"name": src})

        task = call("pool.snapshottask.create", {**TASK_DATA, "dataset": src})
        try:
            # Export without cascade disables the attachment via `toggle(attachments, False)`.
            call("pool.export", new_pool["id"], job=True)
            assert call("pool.snapshottask.get_instance", task["id"])["enabled"] is False

            # Re-import re-enables the attachment via `toggle(attachments, True)`.
            call("pool.import_pool", {"guid": new_pool["guid"], "name": pool_name}, job=True)
            assert call("pool.snapshottask.get_instance", task["id"])["enabled"] is True
        finally:
            call("pool.snapshottask.delete", task["id"])
