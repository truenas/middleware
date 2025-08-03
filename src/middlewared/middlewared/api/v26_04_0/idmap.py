from middlewared.api.base import BaseModel
from typing import Literal


__all__ = [
    'IdmapDomainClearIdmapCacheArgs', 'IdmapDomainClearIdmapCacheResult',
]


class IdmapDomainClearIdmapCacheArgs(BaseModel):
    pass


class IdmapDomainClearIdmapCacheResult(BaseModel):
    result: Literal[None]
