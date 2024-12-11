from middlewared.api.base import BaseModel, Excluded, excluded_field
from .pool import PoolEntry


__all__ = ["BootGetStateArgs", "BootGetStateResult"]


class BootGetState(PoolEntry):
    id: Excluded = excluded_field()
    guid: Excluded = excluded_field()


class BootGetStateArgs(BaseModel):
    pass


class BootGetStateResult(BaseModel):
    result: BootGetState
