from middlewared.api.base import BaseModel


__all__ = ["SystemGeneralKbdmapChoicesArgs", "SystemGeneralKbdmapChoicesResult",]


class SystemGeneralKbdmapChoicesArgs(BaseModel):
    pass


class SystemGeneralKbdmapChoicesResult(BaseModel):
    result: dict[str, str]
