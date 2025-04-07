from middlewared.api.base import BaseModel
from typing import Literal


__all__ = [
    'IdmapCacheClearArgs', 'IdmapCacheClearResult',
]


class IdmapCacheClearArgs(BaseModel):
    pass


class IdmapCacheClearResult(BaseModel):
    result: Literal[None]
