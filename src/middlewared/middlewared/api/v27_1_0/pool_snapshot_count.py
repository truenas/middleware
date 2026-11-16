from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = ["PoolDatasetSnapshotCountArgs", "PoolDatasetSnapshotCountResult",]


class PoolDatasetSnapshotCountArgs(BaseModel):
    dataset: str = Field(description="The dataset path to count snapshots for.")


class PoolDatasetSnapshotCountResult(BaseModel):
    result: int = Field(description="The number of snapshots for the specified dataset.")
