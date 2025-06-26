import contextlib
import random
import string

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.keychain import localhost_ssh_credentials
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call, pool, ssh


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
