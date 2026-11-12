from middlewared.api.base import BaseModel


__all__ = [
    'IdmapDomainClearIdmapCacheArgs', 'IdmapDomainClearIdmapCacheResult',
]


class IdmapDomainClearIdmapCacheArgs(BaseModel):
    pass


class IdmapDomainClearIdmapCacheResult(BaseModel):
    result: None
