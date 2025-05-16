from middlewared.api.base import BaseModel


__all__ = ["PoolDatasetSnapshotCountArgs", "PoolDatasetSnapshotCountResults",]


class PoolDatasetSnapshotCountArgs(BaseModel):
    dataset: str


class PoolDatasetSnapshotCountResults(BaseModel):
    result: int
