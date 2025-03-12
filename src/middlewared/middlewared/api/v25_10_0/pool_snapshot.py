from typing import Any, Literal

from middlewared.api.base import BaseModel


__all__ = ["PoolSnapshotEntry"]


class PoolSnapshotEntryPropertyFields(BaseModel):
    value: str
    rawvalue: str
    source: Literal["INHERITED", "NONE", "DEFAULT"]
    parsed: Any


class PoolSnapshotEntry(BaseModel):
    properties: dict[str, PoolSnapshotEntryPropertyFields]
    pool: str
    name: str
    type: Literal["SNAPSHOT"]
    snapshot_name: str
    dataset: str
    id: str
    createtxg: str
