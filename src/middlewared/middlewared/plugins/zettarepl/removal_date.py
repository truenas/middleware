from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import errno
import subprocess
from typing import TYPE_CHECKING, Any

from dateutil.tz import tzlocal
from zettarepl.snapshot.list import list_snapshots
from zettarepl.snapshot.name import parse_snapshot_name
from zettarepl.snapshot.task.snapshot_owner import PeriodicSnapshotTaskSnapshotOwner
from zettarepl.snapshot.task.task import PeriodicSnapshotTask
from zettarepl.transport.interface import ExecException
from zettarepl.transport.local import LocalShell

from middlewared.api.current import PeriodicSnapshotTaskEntry
from middlewared.service.part import ServicePart
from middlewared.service_exception import CallError
from middlewared.utils.time_utils import utc_now

from .definition import periodic_snapshot_task_definition

if TYPE_CHECKING:
    from middlewared.main import Middleware
    from middlewared.service import ServiceContext


class ZettareplRemovalDatePart(ServicePart):
    def __init__(self, context: ServiceContext) -> None:
        super().__init__(context)

        self.removal_dates: defaultdict[str, dict[str, datetime]] = defaultdict(dict)
        self.removal_dates_loaded = False

    def load_removal_dates(self, pool: str | None = None) -> None:
        property_name = self.call_sync2(self.s.pool.snapshottask.removal_date_property)
        cmd = ["zfs", "list", "-t", "snapshot", "-H", "-o", f"name,{property_name}"]
        if pool is not None:
            cmd.extend(["-r", pool])
            removal_dates = defaultdict(dict, self.removal_dates)
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
                parsed_destroy_at = datetime.fromisoformat(destroy_at)
            except Exception as e:
                self.logger.warning("Error parsing snapshot %r %s: %r", snapshot, property_name, e)
                continue

            removal_dates[snapshot_pool][snapshot] = parsed_destroy_at

        self.removal_dates = removal_dates
        self.removal_dates_loaded = True

    def get_removal_dates(self) -> dict[str, datetime] | None:
        if not self.removal_dates_loaded:
            return None

        return dict(sum([list(d.items()) for d in self.removal_dates.values()], []))

    def periodic_snapshot_task_snapshots(self, task: PeriodicSnapshotTaskEntry) -> set[str]:
        try:
            snapshots = list_snapshots(LocalShell(), task.dataset, task.recursive)
        except ExecException:
            raise CallError(f"Dataset {task.dataset!r} does not exist", errno.ENOENT)

        zettarepl_task = PeriodicSnapshotTask.from_data(
            None,  # type: ignore[arg-type]
            periodic_snapshot_task_definition(task),
        )
        snapshot_owner = PeriodicSnapshotTaskSnapshotOwner(utc_now(), zettarepl_task)

        task_snapshots = set()
        for snapshot in snapshots:
            if snapshot_owner.owns_dataset(snapshot.dataset):
                try:
                    parsed_snapshot_name = parse_snapshot_name(snapshot.name, task.naming_schema)
                except ValueError:
                    pass
                else:
                    if snapshot_owner.owns_snapshot(snapshot.dataset, parsed_snapshot_name):
                        task_snapshots.add(str(snapshot))

        return task_snapshots

    def fixate_removal_date(self, datasets: dict[str, list[str]], task: PeriodicSnapshotTaskEntry) -> None:
        property_name = self.call_sync2(self.s.pool.snapshottask.removal_date_property)
        zettarepl_task = PeriodicSnapshotTask.from_data(
            None,  # type: ignore[arg-type]
            periodic_snapshot_task_definition(task),
        )
        for dataset, snapshots in datasets.items():
            for snapshot in snapshots:
                try:
                    parsed_snapshot_name = parse_snapshot_name(snapshot, task.naming_schema)
                except ValueError as e:
                    self.logger.error("Unexpected error parsing snapshot name %r with naming schema %r: %r",
                                      snapshot, task.naming_schema, e)
                    continue

                assert parsed_snapshot_name.datetime is not None
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
                    self.logger.warning("Error setting snapshot %s@%s removal date: %r", dataset, snapshot, e.stderr)
                else:
                    self.removal_dates[k1][k2] = destroy_at

    def annotate_snapshots(self, snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        property_name = self.call_sync2(self.s.pool.snapshottask.removal_date_property)
        snapshot_owners = [
            PeriodicSnapshotTaskSnapshotOwner(
                utc_now(),
                PeriodicSnapshotTask.from_data(
                    task.id,  # type: ignore[arg-type]
                    periodic_snapshot_task_definition(task),
                ),
            )
            for task in self.call_sync2(self.s.pool.snapshottask.query, [["enabled", "=", True]])
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
                            assert parsed_snapshot_name.datetime is not None
                            destroy_at = (
                                parsed_snapshot_name.datetime + snapshot_owner.periodic_snapshot_task.lifetime
                            )

                            if task_destroy_at is None or task_destroy_at < destroy_at:
                                task_destroy_at = destroy_at
                                task_destroy_at_id = snapshot_owner.periodic_snapshot_task.id

            property_destroy_at = None
            user_properties = snapshot.pop("user_properties", {})

            if property_name in user_properties:
                try:
                    property_destroy_at = datetime.fromisoformat(user_properties[property_name])
                except Exception:
                    self.logger.warning(
                        "Error parsing snapshot %r %s",
                        snapshot["name"],
                        property_name,
                        exc_info=True,
                    )

            if task_destroy_at is not None and property_destroy_at is not None:
                if task_destroy_at < property_destroy_at:
                    task_destroy_at = None
                else:
                    property_destroy_at = None

            if task_destroy_at is not None:
                snapshot["retention"] = {
                    "datetime": task_destroy_at.replace(tzinfo=tzlocal()),
                    "source": "periodic_snapshot_task",
                    "periodic_snapshot_task_id": task_destroy_at_id,
                }
            elif property_destroy_at is not None:
                snapshot["retention"] = {
                    "datetime": property_destroy_at.replace(tzinfo=tzlocal()),
                    "source": "property",
                }
            else:
                snapshot["retention"] = None

        return snapshots


async def pool_configuration_change(middleware: Middleware, *args: Any, **kwargs: Any) -> None:
    middleware.create_task(middleware.call2(middleware.services.zettarepl.load_removal_dates))


async def setup(middleware: Middleware) -> None:
    middleware.create_task(middleware.call2(middleware.services.zettarepl.load_removal_dates))
    middleware.register_hook("pool.post_import", pool_configuration_change)
