from middlewared.api.base import BaseModel


__all__ = ["PoolDatasetSnapshotCountArgs", "PoolDatasetSnapshotCountResult",]


class PoolDatasetSnapshotCountArgs(BaseModel):
    dataset: str
    """The dataset path to count snapshots for."""


class PoolDatasetSnapshotCountResult(BaseModel):
    result: int
    """The number of snapshots for the specified dataset."""
