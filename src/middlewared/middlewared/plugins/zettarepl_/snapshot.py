import asyncio
from collections import defaultdict
from datetime import datetime
import subprocess

import isodate

from middlewared.service import Service

from zettarepl.snapshot.list import list_snapshots
from zettarepl.snapshot.name import parse_snapshot_name
from zettarepl.snapshot.task.snapshot_owner import PeriodicSnapshotTaskSnapshotOwner
from zettarepl.snapshot.task.task import PeriodicSnapshotTask
from zettarepl.transport.local import LocalShell


class ZettareplService(Service):
    removal_dates = defaultdict(dict)
    removal_dates_loaded = False

    def load_removal_dates(self, pool=None):
        property_name = self.middleware.call_sync("pool.snapshottask.removal_date_property")
        cmd = ["zfs", "list", "-t", "snapshot", "-H", "-o", f"name,{property_name}"]
        if pool is not None:
            cmd.extend(["-r", pool])
            removal_dates = self.removal_dates.copy()
            removal_dates[pool] = {}
        else:
            removal_dates = defaultdict(dict)

        for snapshot, destroy_at in map(lambda s: s.split("\t", 1), subprocess.run(
            cmd, check=True, capture_output=True, encoding="utf-8", errors="ignore",
        ).stdout.splitlines()):
            if destroy_at == "-":
                continue

            snapshot_pool = snapshot.split("/")[0]

            try:
                destroy_at = isodate.parse_datetime(destroy_at)
            except Exception as e:
                self.middleware.logger.warning("Error parsing snapshot %r %s: %r", snapshot, property_name, e)
                continue

            removal_dates[snapshot_pool][snapshot] = destroy_at

        self.removal_dates = removal_dates
        self.removal_dates_loaded = True

    def get_removal_dates(self):
        if not self.removal_dates_loaded:
            return None

        return dict(sum([list(d.items()) for d in self.removal_dates.values()], []))

    def periodic_snapshot_task_snapshots(self, task):
        snapshots = list_snapshots(LocalShell(), task["dataset"], task["recursive"])
        zettarepl_task = PeriodicSnapshotTask.from_data(None, self.middleware.call_sync(
            "zettarepl.periodic_snapshot_task_definition", task,
        ))
        snapshot_owner = PeriodicSnapshotTaskSnapshotOwner(datetime.utcnow(), zettarepl_task)

        task_snapshots = set()
        for snapshot in snapshots:
            if snapshot_owner.owns_dataset(snapshot.dataset):
                try:
                    parsed_snapshot_name = parse_snapshot_name(snapshot.name, task["naming_schema"])
                except ValueError:
                    pass
                else:
                    if snapshot_owner.owns_snapshot(snapshot.dataset, parsed_snapshot_name):
                        task_snapshots.add(str(snapshot))

        return task_snapshots

    def fixate_removal_date(self, datasets, task):
        property_name = self.middleware.call_sync("pool.snapshottask.removal_date_property")
        zettarepl_task = PeriodicSnapshotTask.from_data(None, self.middleware.call_sync(
            "zettarepl.periodic_snapshot_task_definition", task,
        ))
        for dataset, snapshots in datasets.items():
            for snapshot in snapshots:
                try:
                    parsed_snapshot_name = parse_snapshot_name(snapshot, task["naming_schema"])
                except ValueError as e:
                    self.middleware.logger.error("Unexpected error parsing snapshot name %r with naming schema %r: %r",
                                                 snapshot, task["naming_schema"], e)
                else:
                    destroy_at = parsed_snapshot_name.datetime + zettarepl_task.lifetime

                    k1 = dataset.split("/")[0]
                    k2 = f"{dataset}@{snapshot}"
                    existing_destroy_at = self.removal_dates.get(k1, {}).get(k2)
                    if existing_destroy_at is not None and existing_destroy_at >= destroy_at:
                        continue

                    try:
                        subprocess.run(
                            ["zfs", "set", f"{property_name}={destroy_at.isoformat()}", f"{dataset}@{snapshot}"],
                            check=True, capture_output=True, encoding="utf-8", errors="ignore",
                        )
                    except subprocess.CalledProcessError as e:
                        self.middleware.logger.warning("Error setting snapshot %s@%s removal date: %r", dataset,
                                                       snapshot, e.stderr)
                    else:
                        self.removal_dates[k1][k2] = destroy_at

    def annotate_snapshots(self, snapshots):
        property_name = self.middleware.call_sync("pool.snapshottask.removal_date_property")
        zettarepl_tasks = [
            PeriodicSnapshotTask.from_data(task["id"], self.middleware.call_sync(
                "zettarepl.periodic_snapshot_task_definition", task,
            ))
            for task in self.middleware.call_sync("pool.snapshottask.query", [["enabled", "=", True]])
        ]
        snapshot_owners = [
            PeriodicSnapshotTaskSnapshotOwner(datetime.utcnow(), zettarepl_task)
            for zettarepl_task in zettarepl_tasks
        ]

        for snapshot in snapshots:
            task_destroy_at = None
            task_destroy_at_id = None
            for snapshot_owner in snapshot_owners:
                if snapshot_owner.owns_dataset(snapshot["dataset"]):
                    try:
                        parsed_snapshot_name = parse_snapshot_name(
                            snapshot["snapshot_name"], snapshot_owner.periodic_snapshot_task.naming_schema
                        )
                    except ValueError:
                        pass
                    else:
                        if snapshot_owner.owns_snapshot(snapshot["dataset"], parsed_snapshot_name):
                            destroy_at = parsed_snapshot_name.datetime + snapshot_owner.periodic_snapshot_task.lifetime

                            if task_destroy_at is None or task_destroy_at < destroy_at:
                                task_destroy_at = destroy_at
                                task_destroy_at_id = snapshot_owner.periodic_snapshot_task.id

            property_destroy_at = None
            if property_name in snapshot["properties"]:
                try:
                    property_destroy_at = isodate.parse_datetime(snapshot["properties"][property_name]["value"])
                except Exception as e:
                    self.middleware.logger.warning("Error parsing snapshot %r %s: %r", snapshot["name"], property_name,
                                                   e)

            if task_destroy_at is not None and property_destroy_at is not None:
                if task_destroy_at < property_destroy_at:
                    task_destroy_at = None
                else:
                    property_destroy_at = None

            if task_destroy_at is not None:
                snapshot["retention"] = {
                    "datetime": task_destroy_at,
                    "source": "periodic_snapshot_task",
                    "periodic_snapshot_task_id": task_destroy_at_id,
                }
            elif property_destroy_at is not None:
                snapshot["retention"] = {
                    "datetime": property_destroy_at,
                    "source": "property",
                }
            else:
                snapshot["retention"] = None

        return snapshots


async def pool_configuration_change(middleware, *args, **kwargs):
    asyncio.ensure_future(middleware.call("zettarepl.load_removal_dates"))


async def setup(middleware):
    asyncio.ensure_future(middleware.call("zettarepl.load_removal_dates"))

    middleware.register_hook("pool.post_import", pool_configuration_change)
