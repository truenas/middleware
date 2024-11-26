from pydantic import PositiveInt

from middlewared.api.base import BaseModel


__all__ = []


class PoolScrubEntry(BaseModel):
    pool: PositiveInt
    threshold: 