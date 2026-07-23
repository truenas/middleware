import contextlib
import random
import string

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.keychain import localhost_ssh_credentials
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, pool, ssh

from truenas_api_client import ClientException


BASE_REPLICATION = {
    "direction": "PUSH",
    "transport": "LOCAL",
    "source_datasets": ["data"],
    "target_dataset": "data",
    "recursive": False,
    "auto": False,
    "retention_policy": "NONE",
}


@pytest.fixture(scope="module")
def ssh_credentials():
    with localhost_ssh_credentials(username="root") as c:
        yield c


@pytest.fixture(scope="module")
def periodic_snapshot_tasks():
    result = {}
    with contextlib.ExitStack() as stack:
        for k, v in {
            "data-recursive": {
                "dataset": "tank/data",
                "recursive": True,
                "lifetime_value": 1,
                "lifetime_unit": "WEEK",
                "naming_schema": "auto-%Y%m%d.%H%M%S-1w",
                "schedule": {},
            },
            "data-work-nonrecursive": {
                "dataset": "tank/data/work",
                "recursive": False,
                "lifetime_value": 1,
                "lifetime_unit": "WEEK",
                "naming_schema": "auto-%Y%m%d.%H%M%S-1w",
                "schedule": {},
            },

            "exclude": {
                "dataset": "tank/exclude",
                "recursive": True,
                "exclude": ["tank/exclude/work/garbage"],
                "lifetime_value": 1,
                "lifetime_unit": "WEEK",
                "naming_schema": "snap-%Y%m%d-%H%M-1w",
                "schedule": {},
            },
        }.items():
            stack.enter_context(dataset(v["dataset"].removeprefix("tank/")))
            result[k] = stack.enter_context(snapshot_task(v))

        yield result


@pytest.mark.parametrize("req,error", [
    # Push + naming-schema
    (dict(naming_schema=["snap-%Y%m%d-%H%M-1m"]), "naming_schema"),

    # Auto with both periodic snapshot task and schedule
    (dict(periodic_snapshot_tasks=["data-recursive"], schedule={"minute": "*/2"}, auto=True), None),
    # Auto with periodic snapshot task
    (dict(periodic_snapshot_tasks=["data-recursive"], auto=True), None),
    # Auto with schedule
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-2m"], schedule={"minute": "*/2"}, auto=True), None),
    # Auto without periodic snapshot task or schedule
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-2m"], auto=True), "auto"),

    # Pull + periodic snapshot tasks
    (dict(direction="PULL", periodic_snapshot_tasks=["data-recursive"]), "periodic_snapshot_tasks"),
    # Pull with naming schema
    (dict(direction="PULL", naming_schema=["snap-%Y%m%d-%H%M-1w"]), None),
    # Pull + also_include_naming_schema
    (dict(direction="PULL", naming_schema=["snap-%Y%m%d-%H%M-1w"], also_include_naming_schema=["snap-%Y%m%d-%H%M-2m"]),
     "also_include_naming_schema"),
    # Pull + hold_pending_snapshots
    (dict(direction="PULL", naming_schema=["snap-%Y%m%d-%H%M-1w"], hold_pending_snapshots=True),
     "hold_pending_snapshots"),

    # SSH+Netcat
    (dict(periodic_snapshot_tasks=["data-recursive"],
          transport="SSH+NETCAT", ssh_credentials=True, netcat_active_side="LOCAL", netcat_active_side_port_min=1024,
          netcat_active_side_port_max=50000),
     None),
    # Bad netcat_active_side_port_max
    (dict(transport="SSH+NETCAT", ssh_credentials=True, netcat_active_side="LOCAL", netcat_active_side_port_min=60000,
          netcat_active_side_port_max=50000),
     "netcat_active_side_port_max"),
    # SSH+Netcat + compression
    (dict(transport="SSH+NETCAT", compression="LZ4"), "compression"),
    # SSH+Netcat + speed limit
    (dict(transport="SSH+NETCAT", speed_limit=1024), "speed_limit"),

    # Does not exclude garbage
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=True), "exclude"),
    # Does not exclude garbage
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=True,
          exclude=["tank/exclude/work/garbage"]),
     None),
    # May not exclude if not recursive
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=False), None),
    # Can't replicate excluded dataset
    (dict(source_datasets=["tank/exclude/work/garbage"], periodic_snapshot_tasks=["exclude"]),
     "source_datasets.0"),

    # Non-recursive exclude
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=False,
          exclude=["tank/exclude/work/garbage"]),
     "exclude"),

    # Unrelated exclude
    (dict(source_datasets=["tank/exclude/work"], periodic_snapshot_tasks=["exclude"], recursive=True,
          exclude=["tank/data"]),
     "exclude.0"),

    # Does not require unrelated exclude
    (dict(source_datasets=["tank/exclude/work/important"], periodic_snapshot_tasks=["exclude"], recursive=True),
     None),

    # Custom retention policy
    (dict(periodic_snapshot_tasks=["data-recursive"],
          retention_policy="CUSTOM", lifetime_value=2, lifetime_unit="WEEK"), None),

    # Complex custom retention policy
    (dict(periodic_snapshot_tasks=["data-recursive"],
          retention_policy="CUSTOM", lifetime_value=2, lifetime_unit="WEEK", lifetimes=[
              dict(schedule={"hour": "0"}, lifetime_value=30, lifetime_unit="DAY"),
              dict(schedule={"hour": "0", "dow": "1"}, lifetime_value=1, lifetime_unit="YEAR"),
          ]), None),

    # name_regex
    (dict(name_regex="manual-.+"), None),
    (dict(direction="PULL", name_regex="manual-.+"), None),
    (dict(name_regex="manual-.+",
          retention_policy="CUSTOM", lifetime_value=2, lifetime_unit="WEEK"), "retention_policy"),

    # replicate
    (dict(source_datasets=["tank/data", "tank/data/work"], periodic_snapshot_tasks=["data-recursive"], replicate=True,
          recursive=True, properties=True),
     "source_datasets.1"),
    (dict(source_datasets=["tank/data"], periodic_snapshot_tasks=["data-recursive", "data-work-nonrecursive"],
          replicate=True, recursive=True, properties=True),
     "periodic_snapshot_tasks.1"),

    # Transport/netcat validation for non-netcat (LOCAL) transport
    # netcat_active_side has no sense for non-netcat transport
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], netcat_active_side="LOCAL"), "netcat_active_side"),
    # netcat port fields have no sense for non-netcat transport
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], netcat_active_side_port_min=1024),
     "netcat_active_side_port_min"),
    # Remote credentials have no sense for local replication
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], ssh_credentials=True), "ssh_credentials"),
    # Compression has no sense for local replication
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], compression="LZ4"), "compression"),
    # Speed limit has no sense for local replication
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], speed_limit=1024), "speed_limit"),

    # Automatic pull replication must have a schedule
    (dict(direction="PULL", naming_schema=["snap-%Y%m%d-%H%M-1w"], auto=True), "auto"),

    # Full filesystem replication (replicate) requirements
    # replicate requires recursive
    (dict(source_datasets=["tank/data"], periodic_snapshot_tasks=["data-recursive"], replicate=True, recursive=False,
          properties=True, retention_policy="SOURCE"),
     "recursive"),
    # replicate does not support exclude
    (dict(source_datasets=["tank/data"], periodic_snapshot_tasks=["data-recursive"], replicate=True, recursive=True,
          properties=True, retention_policy="SOURCE", exclude=["tank/data/work"]),
     "exclude"),
    # replicate requires properties
    (dict(source_datasets=["tank/data"], periodic_snapshot_tasks=["data-recursive"], replicate=True, recursive=True,
          properties=False, retention_policy="SOURCE"),
     "properties"),

    # Encryption enabled (not inherited) requires key details
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], encryption=True, encryption_inherit=False),
     "encryption_key"),
    # Encryption enabled with some (but not all) key details provided
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], encryption=True, encryption_inherit=False,
          encryption_key="0" * 64, encryption_key_format="HEX"),
     "encryption_key_location"),

    # Schedule requires auto
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], schedule={"minute": "*/2"}), "schedule"),
    # only_matching_schedule requires a schedule
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], only_matching_schedule=True), "only_matching_schedule"),

    # name_regex validation
    # Invalid regex
    (dict(name_regex="("), "name_regex"),
    # name_regex can't be used with periodic snapshot tasks
    (dict(name_regex="manual-.+", periodic_snapshot_tasks=["data-recursive"]), "name_regex"),
    # name_regex can't be used with naming schema
    (dict(name_regex="manual-.+", also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"]), "name_regex"),

    # Retention lifetime validation
    # CUSTOM retention requires lifetime_value
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], retention_policy="CUSTOM", lifetime_unit="WEEK"),
     "lifetime_value"),
    # CUSTOM retention requires lifetime_unit
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], retention_policy="CUSTOM", lifetime_value=2),
     "lifetime_unit"),
    # Non-custom retention forbids lifetime_value
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], lifetime_value=2), "lifetime_value"),
    # Non-custom retention forbids lifetime_unit
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"], lifetime_unit="WEEK"), "lifetime_unit"),
    # Non-custom retention forbids lifetimes
    (dict(also_include_naming_schema=["snap-%Y%m%d-%H%M-1w"],
          lifetimes=[dict(schedule={"hour": "0"}, lifetime_value=30, lifetime_unit="DAY")]),
     "lifetimes"),
])
def test_create_replication(ssh_credentials, periodic_snapshot_tasks, req, error):
    if "ssh_credentials" in req:
        req["ssh_credentials"] = ssh_credentials["credentials"]["id"]

    if "periodic_snapshot_tasks" in req:
        req["periodic_snapshot_tasks"] = [periodic_snapshot_tasks[k]["id"] for k in req["periodic_snapshot_tasks"]]

    name = "".join(random.choice(string.ascii_letters) for _ in range(64))
    data = dict(BASE_REPLICATION, name=name, **req)

    if error:
        with pytest.raises(ValidationErrors) as ve:
            with replication_task(data):
                pass

        assert any(e.attribute == f"replication_create.{error}" for e in ve.value.errors)
    else:
        with replication_task(data) as replication:
            restored = call("replication.restore", replication["id"], {
                "name": f"restore {name}",
                "target_dataset": "data/restore",
            })
            call("replication.delete", restored["id"])


@pytest.mark.parametrize("data,path,include", [
    ({"direction": "PUSH", "source_datasets": ["data/child"]}, "/mnt/data/", True),
    ({"direction": "PUSH", "source_datasets": ["data/child"]}, "/mnt/data/child", True),
    ({"direction": "PUSH", "source_datasets": ["data/child"]}, "/mnt/data/child/work", False),
    ({"direction": "PULL", "target_dataset": "data/child"}, "/mnt/data", True),
    ({"direction": "PULL", "target_dataset": "data/child"}, "/mnt/data/child", True),
    ({"direction": "PULL", "target_dataset": "data/child"}, "/mnt/data/child/work", False),
])
def test_query_attachment_delegate(ssh_credentials, data, path, include):
    data = {
        "name": "Test",
        "transport": "SSH",
        "source_datasets": ["source"],
        "target_dataset": "target",
        "recursive": False,
        "name_regex": ".+",
        "auto": False,
        "retention_policy": "NONE",
        **data,
    }
    if data["transport"] == "SSH":
        data["ssh_credentials"] = ssh_credentials["credentials"]["id"]

    with replication_task(data) as t:
        result = call("pool.dataset.query_attachment_delegate", "replication", path, True)
        if include:
            assert len(result) == 1
            assert result[0]["id"] == t["id"]
        else:
            assert len(result) == 0


@pytest.mark.parametrize("exclude_mountpoint_property", [True, False])
def test_run_onetime__exclude_mountpoint_property(exclude_mountpoint_property):
    with dataset("src") as src:
        with dataset("src/legacy") as src_legacy:
            ssh(f"zfs set mountpoint=legacy {src_legacy}")
            ssh(f"zfs snapshot -r {src}@2022-01-01-00-00-00")

            try:
                call("replication.run_onetime", {
                    "direction": "PUSH",
                    "transport": "LOCAL",
                    "source_datasets": [src],
                    "target_dataset": f"{pool}/dst",
                    "recursive": True,
                    "also_include_naming_schema": ["%Y-%m-%d-%H-%M-%S"],
                    "retention_policy": "SOURCE",
                    "replicate": True,
                    "readonly": "IGNORE",
                    "exclude_mountpoint_property": exclude_mountpoint_property
                }, job=True)

                mountpoint = ssh(f"zfs get -H -o value mountpoint {pool}/dst/legacy").strip()
                if exclude_mountpoint_property:
                    assert mountpoint == f"/mnt/{pool}/dst/legacy"
                else:
                    assert mountpoint == "legacy"
            finally:
                ssh(f"zfs destroy -r {pool}/dst", check=False)


def test_run_onetime__no_mount():
    with dataset("src") as src:
        ssh(f"zfs snapshot -r {src}@2022-01-01-00-00-00")

        try:
            call("replication.run_onetime", {
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": f"{pool}/dst",
                "recursive": True,
                "also_include_naming_schema": ["%Y-%m-%d-%H-%M-%S"],
                "retention_policy": "SOURCE",
                "replicate": True,
                "readonly": "IGNORE",
                "mount": False,
            }, job=True)

            assert ssh(f"zfs get -H -o value mounted {pool}/dst").strip() == "no"
        finally:
            ssh(f"zfs destroy -r {pool}/dst", check=False)


def test_disable_task_preserves_state():
    """
    Test that disabling a replication task preserves the last run and state information.

    This test verifies the bug where disabling a replication task incorrectly clears
    all information about the last run and the last snapshot sent, replacing it with
    "never" and "No snapshots sent yet".

    Bug reproduction steps:
    1. Create a replication task
    2. Run it successfully
    3. Verify state contains execution history (datetime, last_snapshot)
    4. Disable the task
    5. BUG: State is cleared to PENDING and last_snapshot is removed
    """
    with dataset("src") as src:
        with dataset("dst") as dst:
            # Create a snapshot
            call("pool.snapshot.create", {
                "dataset": src,
                "name": "2022-01-01-00-00-00",
            })

            # Create a replication task
            task_data = {
                "name": "test_disable_preserves_state",
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": dst,
                "recursive": False,
                "auto": False,
                "retention_policy": "NONE",
                "also_include_naming_schema": ["%Y-%m-%d-%H-%M-%S"],
                "enabled": True,
            }

            with replication_task(task_data) as task:
                # Run the replication task manually
                call("replication.run", task["id"], job=True)

                # Get the task state after run
                task_after_run = call("replication.get_instance", task["id"])

                # Verify that state information exists after the run
                assert task_after_run["state"] is not None, "State should not be None after run"
                assert isinstance(task_after_run["state"], dict), "State should be a dict"

                # Store the state information before disabling
                # The state dict typically contains: 'state', 'datetime', 'last_snapshot', etc.
                state_before_disable = task_after_run["state"].copy()

                # Verify that the task has some state information indicating it ran
                # The state field should not be PENDING after a successful run
                task_state_value = state_before_disable.get("state", "PENDING")
                assert task_state_value != "PENDING", \
                    f"Task state should not be PENDING after manual run, got: {task_state_value}. " \
                    f"Full state: {state_before_disable}"

                # Check that we have meaningful state info - both datetime AND last_snapshot should be present
                assert "datetime" in state_before_disable, \
                    f"State should contain 'datetime' after run. State: {state_before_disable}"
                assert "last_snapshot" in state_before_disable, \
                    f"State should contain 'last_snapshot' after run. State: {state_before_disable}"

                # Disable the task
                call("replication.update", task["id"], {"enabled": False})

                # Get the task state after disabling
                task_after_disable = call("replication.get_instance", task["id"])

                # This is the bug: the state information should be preserved after disabling
                # but currently it gets cleared
                assert task_after_disable["state"] is not None, "State should not be None after disabling"

                # Check if critical state information is preserved
                # The bug causes the state to be reset to PENDING and removes last_snapshot
                state_after_disable = task_after_disable["state"]

                # Verify state field is preserved
                assert state_after_disable.get("state") == state_before_disable.get("state"), \
                    f"State 'state' field should be preserved after disabling. " \
                    f"Before: {state_before_disable.get('state')}, " \
                    f"After: {state_after_disable.get('state')}"

                # Verify datetime is preserved
                assert "datetime" in state_after_disable, \
                    f"State 'datetime' field should be preserved after disabling. " \
                    f"Before: {state_before_disable}, After: {state_after_disable}"

                # Verify last_snapshot is preserved
                assert "last_snapshot" in state_after_disable, \
                    f"State 'last_snapshot' field should be preserved after disabling. " \
                    f"Before: {state_before_disable}, After: {state_after_disable}"


def test_create_invalid_ssh_credentials():
    """Creating a task referencing nonexistent SSH credentials is a validation error."""
    with pytest.raises(ValidationErrors) as ve:
        call("replication.create", {
            "name": "test_invalid_ssh_credentials",
            "direction": "PUSH",
            "transport": "SSH",
            "ssh_credentials": 999999,
            "source_datasets": ["data"],
            "target_dataset": "data",
            "recursive": False,
            "name_regex": ".+",
            "auto": False,
            "retention_policy": "NONE",
        })

    assert any(e.attribute == "replication_create.ssh_credentials" for e in ve.value.errors)


def test_create_nonexistent_periodic_snapshot_task():
    """Binding a nonexistent periodic snapshot task is a validation error."""
    with pytest.raises(ValidationErrors) as ve:
        call("replication.create", {
            "name": "test_nonexistent_snapshot_task",
            "direction": "PUSH",
            "transport": "LOCAL",
            "periodic_snapshot_tasks": [999999],
            "source_datasets": ["data"],
            "target_dataset": "data",
            "recursive": False,
            "auto": False,
            "retention_policy": "NONE",
        })

    assert any(e.attribute == "replication_create.periodic_snapshot_tasks.0" for e in ve.value.errors)


def test_create_disabled_periodic_snapshot_task_binding():
    """An enabled replication task can't be bound to a disabled periodic snapshot task."""
    with dataset("src") as src:
        with snapshot_task({
            "dataset": src,
            "recursive": False,
            "lifetime_value": 1,
            "lifetime_unit": "WEEK",
            "naming_schema": "auto-%Y%m%d.%H%M%S-1w",
            "schedule": {},
            "enabled": False,
        }) as st:
            with pytest.raises(ValidationErrors) as ve:
                call("replication.create", {
                    "name": "test_disabled_snapshot_task",
                    "direction": "PUSH",
                    "transport": "LOCAL",
                    "periodic_snapshot_tasks": [st["id"]],
                    "source_datasets": [src],
                    "target_dataset": "data",
                    "recursive": False,
                    "auto": False,
                    "retention_policy": "NONE",
                    "enabled": True,
                })

            assert any(e.attribute == "replication_create.periodic_snapshot_tasks.0" for e in ve.value.errors)


def test_run_disabled_task():
    """Running a disabled replication task raises an error."""
    with dataset("src") as src:
        with dataset("dst") as dst:
            with replication_task({
                "name": "test_run_disabled",
                "direction": "PUSH",
                "transport": "LOCAL",
                "source_datasets": [src],
                "target_dataset": dst,
                "recursive": False,
                "also_include_naming_schema": ["%Y-%m-%d-%H-%M-%S"],
                "auto": False,
                "retention_policy": "NONE",
                "enabled": False,
            }) as task:
                with pytest.raises(ClientException, match="Task is not enabled"):
                    call("replication.run", task["id"], job=True)


def test_update_ssh_credentials_task(ssh_credentials):
    """Updating a task bound to SSH credentials normalizes the credentials back to their id."""
    with replication_task({
        "name": "test_update_ssh_credentials",
        "direction": "PUSH",
        "transport": "SSH",
        "ssh_credentials": ssh_credentials["credentials"]["id"],
        "source_datasets": ["data"],
        "target_dataset": "data",
        "recursive": False,
        "name_regex": ".+",
        "auto": False,
        "retention_policy": "NONE",
    }) as task:
        updated = call("replication.update", task["id"], {"retries": 3})

        assert updated["retries"] == 3
        assert updated["ssh_credentials"]["id"] == ssh_credentials["credentials"]["id"]


def test_attachment_delegate_delete():
    """Deleting a source dataset removes the replication task via the attachment delegate."""
    with dataset("src") as src:
        task = call("replication.create", {
            "name": "test_attachment_delete",
            "direction": "PUSH",
            "transport": "LOCAL",
            "source_datasets": [src],
            "target_dataset": "data",
            "recursive": False,
            "name_regex": ".+",
            "auto": False,
            "retention_policy": "NONE",
        })

    # Exiting the `dataset` context deletes the source dataset, which drives the attachment
    # delegate to delete the associated replication task.
    assert call("replication.query", [["id", "=", task["id"]]]) == []


ATTACHMENT_TOGGLE_POOL = "test_attachment_toggle"
ATTACHMENT_TOGGLE_SRC = f"{ATTACHMENT_TOGGLE_POOL}/src"


@pytest.mark.parametrize("namespace,data", (
    pytest.param("replication", {
        "name": "test_attachment_toggle",
        "direction": "PUSH",
        "transport": "LOCAL",
        "source_datasets": [ATTACHMENT_TOGGLE_SRC],
        "target_dataset": "data",
        "recursive": False,
        "name_regex": ".+",
        "auto": False,
        "retention_policy": "NONE",
    }, id="replication"),
    pytest.param("pool.snapshottask", {
        "dataset": ATTACHMENT_TOGGLE_SRC,
        "recursive": False,
        "lifetime_value": 1,
        "lifetime_unit": "WEEK",
        "naming_schema": "auto-%Y%m%d.%H%M%S-1w",
        "schedule": {},
        "enabled": True,
    }, id="snapshot_task"),
))
def test_attachment_delegate_toggle(namespace, data):
    """Non-cascade export then re-import disables and re-enables a pool's attachments via the delegate.

    The `snapshot_task` case guards the type-safe `pool.snapshottask` conversion: that delegate returns
    model objects, so the export `enable_on_import` bookkeeping and the re-import re-enable step must not
    subscript attachments like dicts.
    """
    with another_pool({"name": ATTACHMENT_TOGGLE_POOL}) as new_pool:
        call("pool.dataset.create", {"name": ATTACHMENT_TOGGLE_SRC})
        task = call(f"{namespace}.create", data)
        try:
            # Export without cascade disables the attachment via `toggle(attachments, False)`.
            call("pool.export", new_pool["id"], job=True)
            assert call(f"{namespace}.get_instance", task["id"])["enabled"] is False

            # Re-import re-enables the attachment via `toggle(attachments, True)`.
            call("pool.import_pool", {"guid": new_pool["guid"], "name": ATTACHMENT_TOGGLE_POOL}, job=True)
            assert call(f"{namespace}.get_instance", task["id"])["enabled"] is True
        finally:
            call(f"{namespace}.delete", task["id"])


def test_query_check_dataset_encryption_keys():
    """Querying with `check_dataset_encryption_keys` exercises the encryption-key extend path."""
    with dataset("src_enc", {
        "encryption": True,
        "inherit_encryption": False,
        "encryption_options": {"generate_key": True},
    }) as src:
        with replication_task({
            "name": "test_encryption_keys_query",
            "direction": "PUSH",
            "transport": "LOCAL",
            "source_datasets": [src],
            "target_dataset": "data",
            "recursive": True,
            "name_regex": ".+",
            "auto": False,
            "retention_policy": "NONE",
        }) as task:
            result = call("replication.query", [["id", "=", task["id"]]], {
                "get": True,
                "extra": {"check_dataset_encryption_keys": True},
            })

            assert "has_encrypted_dataset_keys" in result
