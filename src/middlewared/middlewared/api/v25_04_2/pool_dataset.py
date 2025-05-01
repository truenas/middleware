from typing import Union

from middlewared.api.base import BaseModel


__all__ = [
    "PoolDatasetDestroySnapshotsArgs", "PoolDatasetDestroySnapshotsResult",
]


class PoolDatasetDestroySnapshotsArgs(BaseModel):
    name: str
    snapshots: "PoolDatasetDestroySnapshotsArgsSnapshots"


class PoolDatasetDestroySnapshotsArgsSnapshots(BaseModel):
    all: bool = False
    recursive: bool = False
    snapshots: list[Union["PoolDatasetDestroySnapshotsArgsSnapshotSpec", str]] = []


class PoolDatasetDestroySnapshotsArgsSnapshotSpec(BaseModel):
    start: str | None = None
    end: str | None = None


class PoolDatasetDestroySnapshotsResult(BaseModel):
    result: list[str]
