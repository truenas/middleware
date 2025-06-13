from middlewared.api.base import BaseModel


__all__ = ["PoolDatasetSnapshotCountArgs", "PoolDatasetSnapshotCountResult",]


class PoolDatasetSnapshotCountArgs(BaseModel):
    dataset: str


class PoolDatasetSnapshotCountResult(BaseModel):
    result: int
