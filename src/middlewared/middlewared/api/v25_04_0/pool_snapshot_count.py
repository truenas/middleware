from middlewared.api.base import BaseModel


class PoolDatasetSnapshotCountArgs(BaseModel):
    dataset: str


class PoolDatasetSnapshotCountResult(BaseModel):
    result: int
