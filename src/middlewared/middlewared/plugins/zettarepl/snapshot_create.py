from zettarepl.snapshot.create import create_snapshot
from zettarepl.snapshot.snapshot import Snapshot
from zettarepl.transport.local import LocalShell


def create_recursive_snapshot_with_exclude(dataset: str, snapshot: str, exclude: list[str]) -> None:
    create_snapshot(LocalShell(), Snapshot(dataset, snapshot), True, exclude, {})
