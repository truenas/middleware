from middlewared.api.base import BaseModel


class PoolDatasetSnapshotCountArgs(BaseModel):
    dataset: str


class PoolDatasetSnapshotCountResults(BaseModel):
    result: int
